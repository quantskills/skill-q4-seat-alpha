"""Q4 回测：席位因子多空组合、IC/IR、年度收益与相对 CTA 的增量。

执行口径：每周最后一个交易日定信号，下一交易日开盘换仓，双边 1.5bp；
Top/Bottom 各 3 个品种等权，周内持有。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data as data_layer  # noqa: E402

PRODUCTS = data_layer.PRODUCTS
SIGNAL_COLS = ("f1", "f5", "f6", "f8", "seat", "carry")
DEFAULTS = {
    "top_k": 3,
    "cost_bps": 1.5,
    "lag": 0,
    "products": PRODUCTS,
    "min_products": 6,
}


def validate_input(input_data) -> None:
    if not isinstance(input_data, dict):
        raise TypeError("input_data 必须是 dict")
    for key in ("panel", "cta_returns"):
        if key not in input_data:
            raise ValueError(f"input_data 缺少字段: {key}")
    panel = input_data["panel"]
    if not isinstance(panel, pd.DataFrame) or panel.empty:
        raise ValueError("panel 必须是非空 DataFrame")
    missing = {"date", "product", "seat"} - set(panel.columns)
    if missing:
        raise ValueError(f"panel 缺少字段: {sorted(missing)}")
    rets = input_data["cta_returns"]
    if not isinstance(rets, pd.DataFrame) or rets.empty:
        raise ValueError("cta_returns 必须是非空 DataFrame")
    missing = {"date", "ret"} - set(rets.columns)
    if missing:
        raise ValueError(f"cta_returns 缺少字段: {sorted(missing)}")


def _validate_config(config: dict | None) -> dict:
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise TypeError("config 必须是 dict 或 None")
    unknown = set(config) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"config 含未知字段: {sorted(unknown)}")
    cfg = dict(DEFAULTS)
    cfg.update(config)
    if not isinstance(cfg["top_k"], int) or cfg["top_k"] <= 0:
        raise ValueError("top_k 必须是正整数")
    if not isinstance(cfg["cost_bps"], (int, float)) or cfg["cost_bps"] < 0:
        raise ValueError("cost_bps 必须是非负数")
    if not isinstance(cfg["min_products"], int) or cfg["min_products"] < 2 * cfg["top_k"]:
        raise ValueError("min_products 必须 >= 2 * top_k")
    if cfg["lag"] not in (0, 1, 2):
        raise ValueError("lag 只能是 0 / 1 / 2")
    return cfg


def weekly_marks(dates: list[str]) -> list[int]:
    iso = pd.to_datetime(dates).isocalendar()
    keys = list(zip(iso.year.tolist(), iso.week.tolist()))
    marks, last = [], None
    for i, k in enumerate(keys):
        if last is not None and k != last:
            marks.append(i - 1)
        last = k
    marks.append(len(dates) - 1)
    return marks


def long_short_returns(panel: pd.DataFrame, rets: pd.DataFrame, signal_col: str,
                       cfg: dict) -> tuple[pd.DataFrame, dict]:
    dates = rets.index.tolist()
    daily_ret = rets[PRODUCTS].values
    top_k, cost_bps = cfg["top_k"], cfg["cost_bps"]
    marks = weekly_marks(dates)
    sig_dates = [dates[i] for i in marks if dates[i] in set(panel["date"])]
    curve, ics = [], []
    weights = pd.Series(0.0, index=PRODUCTS)
    turnover_total = 0.0

    for j, d in enumerate(sig_dates):
        if d not in rets.index:
            continue
        idx = dates.index(d)
        exec_idx = idx + 1
        if exec_idx >= len(dates):
            continue
        day = panel[panel["date"] == d]
        s = day.set_index("product")[signal_col].reindex(PRODUCTS).dropna()
        if len(s) < cfg["min_products"]:
            continue
        w = pd.Series(0.0, index=PRODUCTS)
        w[s.nlargest(top_k).index] = 1 / top_k
        w[s.nsmallest(top_k).index] = -1 / top_k

        if j + 1 < len(sig_dates):
            end_idx = dates.index(sig_dates[j + 1]) + 1
        else:
            end_idx = len(dates)
        ret_week = daily_ret[exec_idx:end_idx]
        if len(ret_week) == 0:
            continue
        contrib = (ret_week * w.values).sum(axis=1)
        turnover = float(np.abs(w - weights).sum())
        turnover_total += turnover
        contrib[0] -= turnover * cost_bps / 10000
        weights = w
        for k, r in enumerate(contrib):
            curve.append({"date": dates[exec_idx + k], "ret": float(r)})

        fwd = pd.Series(ret_week.sum(axis=0), index=PRODUCTS)
        common = s.index.intersection(fwd.index)
        if len(common) >= 3 and np.std(fwd[common]) > 0:
            ics.append(spearmanr(s[common], fwd[common]).correlation)

    if not curve:
        return pd.DataFrame(columns=["ret"]), {"ic_mean": None, "ic_n": 0, "turnover_x": 0.0}
    df = pd.DataFrame(curve).drop_duplicates("date").set_index("date").sort_index()
    ic_mean = float(np.nanmean(ics)) if ics else None
    return df, {"ic_mean": ic_mean, "ic_n": len(ics),
                "turnover_x": round(turnover_total / max(len(df) / 252, 1e-9), 2)}


def metrics(df: pd.DataFrame, name: str, ic: dict | None = None) -> dict:
    r = df["ret"]
    years = len(r) / 252
    total = float((1 + r).prod() - 1)
    ann = (1 + total) ** (1 / years) - 1 if years > 0 else 0
    vol = float(r.std() * math.sqrt(252))
    curve = (1 + r).cumprod()
    mdd = float((curve / curve.cummax() - 1).min())
    row = {
        "strategy": name,
        "total_return": round(total, 4),
        "annual_return": round(ann, 4),
        "annual_vol": round(vol, 4),
        "sharpe": round(ann / vol, 3) if vol else None,
        "max_drawdown": round(mdd, 4),
        "calmar": round(ann / abs(mdd), 3) if mdd else None,
        "ic_mean": round(ic["ic_mean"], 4) if ic and ic.get("ic_mean") is not None else None,
        "ic_n": ic["ic_n"] if ic else None,
        "turnover_x": ic["turnover_x"] if ic else None,
    }
    return row


def _build_panel_with_carry(panel: pd.DataFrame, carry: pd.DataFrame | None) -> pd.DataFrame:
    if carry is None or carry.empty:
        return panel
    extra = carry[["date", "product", "carry"]].copy()
    merged = panel.merge(extra, on=["date", "product"], how="left")
    # carry 是慢变量：按品种前向填充，避免周内缺失
    merged = merged.sort_values(["product", "date"])
    merged["carry"] = merged.groupby("product")["carry"].ffill()
    return merged.sort_values(["date", "product"]).reset_index(drop=True)


def run(input_data=None, config: dict | None = None) -> dict:
    validate_input(input_data)
    cfg = _validate_config(config)
    panel = input_data["panel"].copy()
    panel["date"] = panel["date"].astype(str)
    if cfg["lag"] and "f1" in panel.columns:
        mapped = {}
        for p, grp in panel.groupby("product"):
            grp = grp.sort_values("date")
            mapped[p] = grp.set_index("date")["seat"].shift(cfg["lag"])
        shifted = pd.concat(mapped).rename("seat").reset_index()
        shifted.columns = ["product", "date", "seat"]
        panel = panel.drop(columns=["seat"]).merge(shifted, on=["date", "product"], how="left")

    panel = _build_panel_with_carry(panel, input_data.get("carry"))

    rets_df = input_data["cta_returns"].copy()
    rets_df["date"] = rets_df["date"].astype(str)
    rets_df = rets_df.set_index("date").sort_index()

    results, stats = {}, {}
    for col in SIGNAL_COLS:
        if col not in panel.columns:
            continue
        df, ic = long_short_returns(panel, rets_df, col, cfg)
        if df.empty:
            continue
        results[col] = df
        stats[col] = ic

    if "seat" not in results:
        raise ValueError("seat 信号没有生成有效回测，请检查因子面板")

    common = sorted(set(results["seat"].index) & set(rets_df.index))
    if "carry" in results:
        common = sorted(set(common) & set(results["carry"].index))
    common = [d for d in common if d in rets_df.index]
    for name in results:
        results[name] = results[name].reindex(common).dropna()
    cta = rets_df.reindex(common)["ret"].dropna()
    common = sorted(set(results["seat"].index) & set(cta.index))
    for name in results:
        results[name] = results[name].reindex(common).dropna()
    cta = cta.reindex(common)

    rows = [metrics(results["seat"], "seat", stats.get("seat")),
            metrics(cta.to_frame("ret"), "cta")]
    for name in ("carry", "f1", "f5", "f6", "f8"):
        if name in results:
            rows.append(metrics(results[name], name, stats.get(name)))

    yearly = []
    all_series = dict(results)
    all_series["cta"] = cta.to_frame("ret")
    for name, df in all_series.items():
        frame = df.copy()
        frame["year"] = frame.index.str[:4]
        for year, grp in frame.groupby("year"):
            yearly.append({"strategy": name, "year": year,
                           "return": round(float((1 + grp["ret"]).prod() - 1), 4)})

    incremental = {}
    for name in ("seat", "carry"):
        if name not in results:
            continue
        joint = pd.concat([results[name]["ret"], cta], axis=1, join="inner")
        joint.columns = ["x", "cta"]
        if len(joint) > 10 and np.var(joint["cta"]) > 0:
            beta = float(np.cov(joint["x"], joint["cta"])[0, 1] / np.var(joint["cta"]))
            alpha_daily = float(joint["x"].mean() - beta * joint["cta"].mean())
            incremental[name] = {
                "beta_to_cta": round(beta, 3),
                "alpha_annual": round(alpha_daily * 252, 4),
                "corr": round(float(joint["x"].corr(joint["cta"])), 3),
            }

    return {
        "metrics": rows,
        "yearly": yearly,
        "incremental": incremental,
        "equity": {name: df["ret"] for name, df in results.items()},
        "cta": cta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 席位因子回测")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    import factor

    if args.data_dir:
        seat, nm = data_layer.load_local(args.data_dir)
    else:
        seat, nm = data_layer.fetch()
    panel = factor.run({"seat_rank": seat, "net_margin": nm})
    baseline = data_layer.load_baseline()
    result = run({"panel": panel, **baseline})
    print(pd.DataFrame(result["metrics"]).to_string(index=False))
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(result["metrics"]).to_csv(out / "metrics.csv", index=False)
        pd.DataFrame(result["yearly"]).to_csv(out / "yearly_returns.csv", index=False)
        (out / "incremental.json").write_text(
            json.dumps(result["incremental"], ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
