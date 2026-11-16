"""Q4 席位因子计算：F1 / F5 / F6 / F8 与等权合成信号。

因子口径（与公开仓库一致）：
  F1 前 20 席位多空变化差（净持仓）
  F5 前 5 席位净保证金集中度（bear_ratio - bull_ratio，60 日时序 z）
  F6 家人席位净保证金占比（反向，截面 rank）
  F8 家人/主力分歧（(major_ratio - family_ratio) × 一致性强度，截面 rank）
合成：四因子逐日截面 z 后等权 0.25 相加，不做样本内权重优化。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data as data_layer  # noqa: E402

FACTOR_ID = "Q4"
FACTOR_NAME = "seat_ensemble"
PRODUCTS = data_layer.PRODUCTS
FAMILY = ["东方财富", "徽商期货", "平安期货"]
MAJOR = ["永安期货", "中信期货", "国泰君安"]
DEFAULTS = {
    "products": PRODUCTS,
    "family_brokers": FAMILY,
    "major_brokers": MAJOR,
    "f1_window": 5,
    "f5_window": 60,
}


def validate_input(input_data) -> None:
    if not isinstance(input_data, dict):
        raise TypeError("input_data 必须是 dict")
    for key in ("seat_rank", "net_margin"):
        if key not in input_data:
            raise ValueError(f"input_data 缺少字段: {key}")
        frame = input_data[key]
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise ValueError(f"input_data['{key}'] 必须是非空 DataFrame")
    seat_cols = {"date", "underlying_symbol", "broker_name", "position_type",
                 "net_position", "net_position_change"}
    nm_cols = {"date", "underlying_symbol", "broker", "net_margin"}
    missing = seat_cols - set(input_data["seat_rank"].columns)
    if missing:
        raise ValueError(f"seat_rank 缺少字段: {sorted(missing)}")
    missing = nm_cols - set(input_data["net_margin"].columns)
    if missing:
        raise ValueError(f"net_margin 缺少字段: {sorted(missing)}")


def _validate_config(config: dict | None) -> dict:
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise TypeError("config 必须是 dict 或 None")
    unknown = set(config) - set(DEFAULTS) - {"data_dir", "output_dir", "baseline_dir"}
    if unknown:
        raise ValueError(f"config 含未知字段: {sorted(unknown)}")
    cfg = dict(DEFAULTS)
    cfg.update(config)
    for key in ("f1_window", "f5_window"):
        if not isinstance(cfg[key], int) or cfg[key] <= 0:
            raise ValueError(f"{key} 必须是正整数")
    for key in ("family_brokers", "major_brokers"):
        if not isinstance(cfg[key], (list, tuple)) or not cfg[key]:
            raise ValueError(f"{key} 必须是非空列表")
    return cfg


def zscore(s: pd.Series) -> pd.Series:
    std = s.std()
    return (s - s.mean()) / std if std and not np.isnan(std) else s * 0


def seat_factors(seat: pd.DataFrame, f1_window: int = 5) -> pd.DataFrame:
    long = seat[seat["position_type"] == "long"].copy()
    short = seat[seat["position_type"] == "short"].copy()
    short["abs_pos"] = short["net_position"].abs()
    short["short_chg"] = -short["net_position_change"]

    lg = long.groupby(["date", "underlying_symbol"]).agg(
        long_total=("net_position", "sum"), long_chg=("net_position_change", "sum"))
    sh = short.groupby(["date", "underlying_symbol"]).agg(
        short_total=("abs_pos", "sum"), short_chg=("short_chg", "sum"))
    df = lg.join(sh, how="outer").fillna(0.0)

    prev_long = df.groupby(level=1)["long_total"].shift(1)
    prev_short = df.groupby(level=1)["short_total"].shift(1)
    df["f1"] = (df["long_chg"] / prev_long.abs().replace(0, np.nan)
                - df["short_chg"] / prev_short.abs().replace(0, np.nan))

    conc = []
    for (date, product), grp in seat.groupby(["date", "underlying_symbol"]):
        vals = grp["net_position"].abs().sort_values(ascending=False).head(20)
        total = vals.sum()
        conc.append({"date": date, "underlying_symbol": product,
                     "conc": float(vals.head(5).sum() / total) if total else np.nan})
    conc_df = pd.DataFrame(conc).set_index(["date", "underlying_symbol"])
    df = df.join(conc_df, how="left")

    fam = seat[seat["broker_name"].isin(FAMILY)].groupby(
        ["date", "underlying_symbol"])["net_position"].sum()
    df = df.join(fam.rename("family_net"), how="left").fillna({"family_net": 0.0})
    df["family_share"] = df["family_net"] / (df["long_total"] + df["short_total"]).replace(0, np.nan)

    df = df.reset_index().rename(columns={"underlying_symbol": "product"})
    df["f1_5d"] = df.groupby("product")["f1"].transform(
        lambda s: s.rolling(f1_window, min_periods=3).mean())
    return df.set_index(["date", "product"]).sort_index()


def netmargin_factors(nm: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    config = config or {}
    family = list(config.get("family_brokers", FAMILY))
    major = list(config.get("major_brokers", MAJOR))
    f5_window = int(config.get("f5_window", 60))
    idx = ["date", "underlying_symbol"]

    total = nm.assign(abs_m=nm["net_margin"].abs()).groupby(idx)["abs_m"].sum().rename("total")
    bull = (nm[nm["net_margin"] > 0].groupby(idx)["net_margin"]
            .apply(lambda s: s.nlargest(5).sum()).rename("bull_top5"))
    bear = (nm[nm["net_margin"] < 0].groupby(idx)["net_margin"]
            .apply(lambda s: s.abs().nlargest(5).sum()).rename("bear_top5"))
    df = pd.concat([total, bull, bear], axis=1).fillna(0.0)
    df = df[df["total"] > 0].copy()
    df["f5_raw"] = (df["bear_top5"] - df["bull_top5"]) / df["total"]
    g = df.groupby(level=1)["f5_raw"]
    mean = g.transform(lambda s: s.rolling(f5_window, min_periods=20).mean())
    std = g.transform(lambda s: s.rolling(f5_window, min_periods=20).std())
    df["f5"] = ((df["f5_raw"] - mean) / std).replace([np.inf, -np.inf], np.nan)

    fam = nm[nm["broker"].isin(family)].groupby(idx)["net_margin"].sum().rename("family_net")
    df = df.join(fam).fillna({"family_net": 0.0})
    df["f6_raw"] = -df["family_net"] / df["total"]
    df["f6"] = df.groupby(level=0)["f6_raw"].rank(pct=True) * 2 - 1

    family_rows = nm[nm["broker"].isin(family)]
    family_bull = (family_rows.assign(v=family_rows["net_margin"].clip(lower=0))
                   .groupby(idx)["v"].sum().rename("family_bull"))
    family_bear = (family_rows.assign(v=(-family_rows["net_margin"]).clip(lower=0))
                   .groupby(idx)["v"].sum().rename("family_bear"))
    major_rows = nm[nm["broker"].isin(major)]
    major_net = major_rows.groupby(idx)["net_margin"].sum().rename("major_net")
    major_bull = (major_rows.assign(v=major_rows["net_margin"].clip(lower=0))
                  .groupby(idx)["v"].sum().rename("major_bull"))
    major_bear = (major_rows.assign(v=(-major_rows["net_margin"]).clip(lower=0))
                  .groupby(idx)["v"].sum().rename("major_bear"))
    df = df.join([family_bull, family_bear, major_net, major_bull, major_bear]).fillna(0.0)
    df = df[(df["major_bull"] + df["major_bear"]) > 0].copy()
    denom = df["total"] + 2 * np.minimum(df["family_bull"], df["family_bear"])
    family_ratio = df["family_net"] / denom
    major_ratio = df["major_net"] / denom
    major_total = df["major_bull"] + df["major_bear"]
    consistency = df[["major_bull", "major_bear"]].max(axis=1) / major_total.replace(0, np.nan)
    strength = (2 * consistency - 1).clip(lower=0, upper=1)
    df["f8_raw"] = (major_ratio - family_ratio) * strength
    df["f8"] = df.groupby(level=0)["f8_raw"].rank(pct=True) * 2 - 1

    return df[["f5", "f6", "f8"]].reset_index().rename(columns={"underlying_symbol": "product"})


def combine(fac: pd.DataFrame) -> pd.DataFrame:
    fac = fac.copy()
    for col in ("f1", "f5", "f6", "f8"):
        fac[col] = pd.to_numeric(fac[col], errors="coerce")
    parts = [fac.groupby("date")[col].transform(zscore) for col in ("f1", "f5", "f6", "f8")]
    fac["seat"] = 0.25 * sum(parts)
    return fac


def run(input_data=None, config: dict | None = None) -> pd.DataFrame:
    validate_input(input_data)
    cfg = _validate_config(config)
    seat = input_data["seat_rank"].copy()
    nm = input_data["net_margin"].copy()
    seat["date"] = seat["date"].astype(str)
    nm["date"] = nm["date"].astype(str)
    products = set(cfg["products"])
    seat = seat[seat["underlying_symbol"].isin(products)]
    nm = nm[nm["underlying_symbol"].isin(products)]

    seat_f = seat_factors(seat, cfg["f1_window"]).reset_index()
    fac_nm = netmargin_factors(nm, cfg)
    fac = seat_f.merge(fac_nm, on=["date", "product"], how="inner")
    fac = combine(fac)
    fac = fac[["date", "product", "f1", "f1_5d", "f5", "f6", "f8", "seat"]]
    return fac.sort_values(["date", "product"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 席位因子计算")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    if args.data_dir:
        seat, nm = data_layer.load_local(args.data_dir)
    else:
        seat, nm = data_layer.fetch()
    panel = run({"seat_rank": seat, "net_margin": nm})
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        panel.to_csv(out / "factor_panel.csv", index=False)
    print(panel.tail(10).to_string(index=False))
    print("rows", len(panel), "dates", panel["date"].nunique(),
          "products", panel["product"].nunique())


if __name__ == "__main__":
    main()
