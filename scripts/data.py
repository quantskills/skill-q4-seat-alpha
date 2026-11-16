"""Q4 数据层：席位因子所需数据 + 冻结 CTA 基线。

数据来源优先级：
1. input_data 传入 seat_rank / net_margin；
2. config["data_dir"] 读取 seat_rank.parquet / net_margin.parquet；
3. PandaData 额定接口现拉。
CTA 基线（收益/信号/carry）随仓库携带，来自 Q2 真实数据快照。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd

PRODUCTS = ["RB", "HC", "I", "J", "JM", "CU", "AL", "ZN", "AU", "AG", "RU",
            "M", "Y", "P", "C", "TA", "MA", "FG"]
BASELINE_DIR = Path(__file__).resolve().parent.parent / "references" / "baseline"


def _retry(fn, *args, attempts: int = 5, **kwargs):
    last = None
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 + attempt)
    raise last


def load_baseline(base_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    base = Path(base_dir) if base_dir else BASELINE_DIR
    rets = pd.read_parquet(base / "cta_returns.parquet")
    sig = pd.read_parquet(base / "cta_signals.parquet")
    carry = pd.read_parquet(base / "carry.parquet")
    rets["date"] = rets["date"].astype(str)
    sig["date"] = sig["date"].astype(str)
    carry["date"] = carry["date"].astype(str)
    return {"cta_returns": rets, "cta_signals": sig, "carry": carry}


def load_local(data_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = Path(data_dir)
    seat = pd.read_parquet(base / "seat_rank.parquet")
    nm = pd.read_parquet(base / "net_margin.parquet")
    seat["date"] = seat["date"].astype(str)
    nm["date"] = nm["date"].astype(str)
    return seat, nm


def _init_panda_data() -> None:
    import panda_data

    username = os.environ.get("PANDA_DATA_USERNAME")
    password = os.environ.get("PANDA_DATA_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "未配置 PandaData 凭据：请设置 PANDA_DATA_USERNAME / PANDA_DATA_PASSWORD，"
            "或通过 input_data / config['data_dir'] 提供本地数据"
        )
    panda_data.init_token(
        username=username,
        password=password,
        base_url=os.environ.get("PANDA_DATA_BASE_URL", "http://pandadata.pandaaiquant.com"),
    )


def _quarters(start_year: int = 2021, end_year: int = 2025):
    months = (1, 4, 7, 10)
    for year in range(start_year, end_year + 1):
        for month in months:
            end_month = min(month + 2, 12)
            last_day = pd.Timestamp(year=year, month=end_month, day=1) + pd.offsets.MonthEnd(0)
            yield f"{year}{month:02d}01", last_day.strftime("%Y%m%d")


def fetch(products: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """通过 PandaData 拉取前 20 席位净持仓榜与席位净保证金。"""
    import panda_data

    products = products or PRODUCTS
    _init_panda_data()

    seat_frames = []
    for product in products:
        for typ in ("long", "short"):
            for start, end in _quarters():
                df = _retry(panda_data.get_future_netposi_rank,
                            start_date=start, end_date=end,
                            underlying_symbol=[product], max_rank=20, type=typ)
                if df is not None and not df.empty:
                    df["position_type"] = typ
                    seat_frames.append(df)
                time.sleep(0.15)
    if not seat_frames:
        raise RuntimeError("PandaData 未返回席位净持仓数据")
    seat = pd.concat(seat_frames, ignore_index=True)
    seat["date"] = seat["date"].astype(str)
    for col in ("net_position", "net_position_change", "rank"):
        seat[col] = pd.to_numeric(seat[col], errors="coerce")
    seat = seat.drop_duplicates(["date", "underlying_symbol", "broker_name", "position_type"])

    margin_frames = []
    for product in products:
        for year in range(2021, 2026):
            df = _retry(panda_data.get_broker_netmarg,
                        start_date=f"{year}0101", end_date=f"{year}1231",
                        broker="", underlying_symbol=[product])
            if df is not None and not df.empty:
                margin_frames.append(df)
            time.sleep(0.15)
    if not margin_frames:
        raise RuntimeError("PandaData 未返回席位净保证金数据")
    nm = pd.concat(margin_frames, ignore_index=True)
    nm["date"] = nm["date"].astype(str)
    nm["net_margin"] = pd.to_numeric(nm["net_margin"], errors="coerce")
    nm = nm.drop_duplicates(["date", "underlying_symbol", "broker"])
    return seat, nm
