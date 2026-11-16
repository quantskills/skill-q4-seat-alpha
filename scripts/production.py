"""Q4 生产产物：把因子面板转换为标准 Alpha Parquet。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

FACTOR_ID = "Q4"
FACTOR_NAME = "seat_ensemble"
TOP_K = 3


def to_production(panel: pd.DataFrame, data_version: str,
                  top_k: int = TOP_K) -> pd.DataFrame:
    frame = panel.dropna(subset=["seat"]).copy()
    frame["date"] = frame["date"].astype(str)
    frame["score"] = frame.groupby("date")["seat"].rank(pct=True) * 100
    frame["rank"] = frame.groupby("date")["seat"].rank(ascending=False, method="min").astype(int)
    n = frame.groupby("date")["seat"].transform("count")
    frame["signal"] = np.where(frame["rank"] <= top_k, "buy",
                               np.where(frame["rank"] > n - top_k, "sell", "hold"))
    frame["confidence"] = (frame["seat"].abs() / 2).clip(upper=1.0).round(4)
    frame["factor_value"] = frame["seat"].astype(float).round(6)
    update_time = datetime.now().astimezone().isoformat(timespec="seconds")

    out = pd.DataFrame({
        "trade_date": frame["date"],
        "asset_type": "future",
        "symbol": frame["product"],
        "factor_id": FACTOR_ID,
        "factor_name": FACTOR_NAME,
        "factor_value": frame["factor_value"],
        "score": frame["score"].round(2),
        "rank": frame["rank"],
        "signal": frame["signal"],
        "confidence": frame["confidence"],
        "data_version": data_version,
        "update_time": update_time,
    })
    out = out.dropna(subset=["factor_value"])
    out = out.drop_duplicates(["trade_date", "symbol", "factor_id"])
    return out.sort_values(["trade_date", "rank"]).reset_index(drop=True)


def write_production(panel: pd.DataFrame, data_version: str,
                     out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else Path(__file__).resolve().parent.parent / "生产产物"
    out.mkdir(parents=True, exist_ok=True)
    frame = to_production(panel, data_version)
    path = out / "数据库.parquet"
    frame.to_parquet(path, index=False)
    return path


def main() -> None:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import data as data_layer
    import factor

    parser = argparse.ArgumentParser(description="生成 Q4 生产 parquet")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()
    if args.data_dir:
        seat, nm = data_layer.load_local(args.data_dir)
        version = f"pandadata-seat:{seat['date'].min()}..{seat['date'].max()}"
    else:
        seat, nm = data_layer.fetch()
        version = f"pandadata-seat:{seat['date'].min()}..{seat['date'].max()}"
    panel = factor.run({"seat_rank": seat, "net_margin": nm})
    path = write_production(panel, version)
    print(path, len(pd.read_parquet(path)))


if __name__ == "__main__":
    main()
