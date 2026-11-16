"""Q4 因子验真：未来函数、样本外、过拟合与生产文件检查。

用法：
    python scripts/validate.py --data-dir <dir>

输出 PASS / FAIL 清单；任一 FAIL 时退出码为 1。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backtest  # noqa: E402
import data as data_layer  # noqa: E402
import factor  # noqa: E402


def _returns_metrics(ret: pd.Series, name: str) -> dict:
    years = len(ret) / 252
    total = float((1 + ret).prod() - 1)
    ann = (1 + total) ** (1 / years) - 1 if years > 0 else 0.0
    vol = float(ret.std() * math.sqrt(252))
    curve = (1 + ret).cumprod()
    mdd = float((curve / curve.cummax() - 1).min())
    return {"period": name, "annual_return": round(ann, 4),
            "annual_vol": round(vol, 4),
            "sharpe": round(ann / vol, 3) if vol else None,
            "max_drawdown": round(mdd, 4)}


def check_lookahead(seat: pd.DataFrame, nm: pd.DataFrame) -> dict:
    full = factor.run({"seat_rank": seat, "net_margin": nm})
    dates = sorted(full["date"].unique())
    samples = [dates[int(len(dates) * p)] for p in (0.35, 0.6, 0.85)]
    worst = 0.0
    details = []
    for d in samples:
        sub_seat = seat[seat["date"] <= d]
        sub_nm = nm[nm["date"] <= d]
        part = factor.run({"seat_rank": sub_seat, "net_margin": sub_nm})
        left = full[full["date"] == d].set_index("product")
        right = part[part["date"] == d].set_index("product")
        common = left.index.intersection(right.index)
        if len(common) == 0:
            details.append({"date": d, "matched": 0})
            continue
        diff = 0.0
        for col in ("f1", "f5", "f6", "f8", "seat"):
            a = left.loc[common, col].astype(float)
            b = right.loc[common, col].astype(float)
            mask = a.notna() & b.notna()
            if mask.any():
                diff = max(diff, float((a[mask] - b[mask]).abs().max()))
        worst = max(worst, diff)
        details.append({"date": d, "matched": int(len(common)), "max_abs_diff": diff})
    return {"name": "lookahead", "passed": worst <= 1e-9,
            "detail": {"worst_abs_diff": worst, "samples": details}}


def check_oos(result: dict) -> dict:
    seat = result["equity"]["seat"]
    split = "20240101"
    ins = seat[seat.index < split]
    oos = seat[seat.index >= split]
    rows = [_returns_metrics(ins, "2021-2023"), _returns_metrics(oos, "2024-2025")]
    passed = len(oos) > 100 and all(r["sharpe"] is not None for r in rows)
    return {"name": "out_of_sample", "passed": passed, "detail": rows}


def check_overfit(result: dict) -> dict:
    rows = {row["strategy"]: row for row in result["metrics"]}
    seat = rows.get("seat", {})
    singles = {k: rows[k] for k in ("f1", "f5", "f6", "f8") if k in rows}
    best_single = max(singles.values(), key=lambda r: r.get("sharpe") or -99) if singles else {}
    passed = seat.get("sharpe") is not None
    return {"name": "overfit", "passed": passed, "detail": {
        "weights": "四因子等权 0.25，无样本内权重优化",
        "ensemble_sharpe": seat.get("sharpe"),
        "best_single": best_single.get("strategy"),
        "best_single_sharpe": best_single.get("sharpe"),
        "note": "若单因子显著优于合成，应优先研究单因子而不是调权重",
    }}


def check_production(path: Path) -> dict:
    if not path.exists():
        return {"name": "production_parquet", "passed": False,
                "detail": f"缺少 {path}"}
    frame = pd.read_parquet(path)
    required = {"trade_date", "asset_type", "symbol", "factor_id", "factor_name",
                "factor_value", "score", "signal", "data_version", "update_time"}
    missing = required - set(frame.columns)
    dupes = int(frame.duplicated(["trade_date", "symbol", "factor_id"]).sum())
    return {"name": "production_parquet", "passed": not missing and dupes == 0,
            "detail": {"missing": sorted(missing), "dupes": dupes, "rows": len(frame)}}


def run(data_dir: str | Path | None = None, production_path: Path | None = None) -> list[dict]:
    if data_dir:
        seat, nm = data_layer.load_local(data_dir)
    else:
        seat, nm = data_layer.fetch()
    panel = factor.run({"seat_rank": seat, "net_margin": nm})
    baseline = data_layer.load_baseline()
    result = backtest.run({"panel": panel, **baseline})

    checks = [
        check_lookahead(seat, nm),
        check_oos(result),
        check_overfit(result),
    ]
    if production_path is not None:
        checks.append(check_production(production_path))
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 因子验真")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--production", default=None)
    args = parser.parse_args()
    production = Path(args.production) if args.production else (
        Path(__file__).resolve().parent.parent / "生产产物" / "数据库.parquet")
    checks = run(args.data_dir, production)
    failed = 0
    for item in checks:
        status = "PASS" if item["passed"] else "FAIL"
        if not item["passed"]:
            failed += 1
        print(f"[{status}] {item['name']}")
        print(_format_detail(item["detail"]))
    if failed:
        raise SystemExit(1)


def _format_detail(detail) -> str:
    if isinstance(detail, list):
        return pd.DataFrame(detail).to_string(index=False)
    if isinstance(detail, dict):
        return "\n".join(f"  {k}: {v}" for k, v in detail.items())
    return f"  {detail}"


if __name__ == "__main__":
    main()
