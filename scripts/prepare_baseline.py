"""从 Q2 项目导出 Q4/Q6 共用的冻结基线（全部来自真实 PandaData 数据）。

用法：
    python scripts/prepare_baseline.py <q2_project_dir>

q2_project_dir 需包含 data/{daily,contracts,dominant}.parquet 与
outputs/{equity_fixed.csv,signals_frozen.csv}。
输出到 references/baseline/：
    cta_returns.parquet  逐日分品种盈亏（按 100 万名义资金归一）
    cta_signals.parquet  冻结信号
    carry.parquet        期限结构 carry（近月/次近月）
    margin.parquet       品种保证金率中位数
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PRODUCTS = ["RB", "HC", "I", "J", "JM", "CU", "AL", "ZN", "AU", "AG", "RU",
            "M", "Y", "P", "C", "TA", "MA", "FG"]
CAPITAL_PER_PRODUCT = 1_000_000.0


def build_carry(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for product in PRODUCTS:
        sub = daily[daily["underlying_symbol"] == product]
        if sub.empty:
            continue
        pivot = sub.pivot_table(index="date", columns="symbol", values="close")
        oi = sub.pivot_table(index="date", columns="symbol", values="open_interest")
        vol = sub.pivot_table(index="date", columns="symbol", values="volume")
        for d in pivot.index:
            if d not in vol.index:
                continue
            row_vol = vol.loc[d]
            row_oi = oi.loc[d]
            valid = [c for c in pivot.columns
                     if row_vol.get(c, 0) > 100 and not pd.isna(pivot.loc[d, c])]
            if len(valid) < 2:
                continue
            valid.sort(key=lambda c: row_oi.get(c, 0), reverse=True)
            near, far = valid[0], valid[1]
            p1, p2 = pivot.loc[d, near], pivot.loc[d, far]
            if p1 and p2 and p2 > 0:
                rows.append({"date": d, "product": product, "carry": (p1 - p2) / p2})
    return pd.DataFrame(rows)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("用法: python scripts/prepare_baseline.py <q2_project_dir>")
    src = Path(sys.argv[1])
    out = Path(__file__).resolve().parent.parent / "references" / "baseline"
    out.mkdir(parents=True, exist_ok=True)

    daily = pd.read_parquet(src / "data" / "daily.parquet")
    contracts = pd.read_parquet(src / "data" / "contracts.parquet")
    dominant = pd.read_parquet(src / "data" / "dominant.parquet")
    daily["date"] = daily["date"].astype(str)
    dominant["date"] = dominant["date"].astype(str)

    eq = pd.read_csv(src / "outputs" / "equity_fixed.csv")
    eq["date"] = eq["date"].astype(str)
    rets = eq[["date", "ret"] + PRODUCTS].copy()
    for p in PRODUCTS:
        rets[p] = rets[p] / CAPITAL_PER_PRODUCT
    rets.to_parquet(out / "cta_returns.parquet", index=False)

    sig = pd.read_csv(src / "outputs" / "signals_frozen.csv")
    sig["date"] = sig["date"].astype(str)
    sig.to_parquet(out / "cta_signals.parquet", index=False)

    carry = build_carry(daily)
    carry.to_parquet(out / "carry.parquet", index=False)

    merged = dominant[dominant["underlying_symbol"].isin(PRODUCTS)].merge(
        contracts[["symbol", "margin_rate"]], on="symbol", how="left")
    margin = (merged.groupby("underlying_symbol")["margin_rate"].median()
              .reindex(PRODUCTS).fillna(0.10).rename("margin_rate").reset_index())
    margin.columns = ["product", "margin_rate"]
    margin.to_parquet(out / "margin.parquet", index=False)

    print("cta_returns", rets.shape, "signals", sig.shape,
          "carry", len(carry), "margin", margin.shape, "->", out)


if __name__ == "__main__":
    main()
