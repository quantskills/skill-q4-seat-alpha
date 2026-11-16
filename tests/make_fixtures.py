"""从真实 PandaData 导出的小样本生成 Q4 测试 fixtures（不生成模拟数据）。

用法：
    python tests/make_fixtures.py <q4_data_dir>

q4_data_dir 需包含 seat_rank.parquet / net_margin.parquet。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PRODUCTS = ["RB", "HC"]
START = "20220101"
END = "20221231"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("用法: python tests/make_fixtures.py <q4_data_dir>")
    src = Path(sys.argv[1])
    out = Path(__file__).resolve().parent / "fixtures"
    out.mkdir(parents=True, exist_ok=True)

    seat = pd.read_parquet(src / "seat_rank.parquet")
    nm = pd.read_parquet(src / "net_margin.parquet")
    seat["date"] = seat["date"].astype(str)
    nm["date"] = nm["date"].astype(str)

    seat = seat[seat["underlying_symbol"].isin(PRODUCTS)
                & seat["date"].between(START, END)].copy()
    nm = nm[nm["underlying_symbol"].isin(PRODUCTS)
            & nm["date"].between(START, END)].copy()
    seat.to_parquet(out / "seat_rank.parquet", index=False)
    nm.to_parquet(out / "net_margin.parquet", index=False)
    print("seat", seat.shape, "net_margin", nm.shape, "->", out)


if __name__ == "__main__":
    main()
