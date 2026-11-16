"""Q4 Alpha 测试：输入校验、因子计算、回测、生产字段与前视检查。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import backtest  # noqa: E402
import data as data_layer  # noqa: E402
import factor  # noqa: E402
import production  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def load_fixture() -> dict:
    return {
        "seat_rank": pd.read_parquet(FIXTURES / "seat_rank.parquet"),
        "net_margin": pd.read_parquet(FIXTURES / "net_margin.parquet"),
    }


class ValidateInputTest(unittest.TestCase):
    def test_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            factor.validate_input(None)

    def test_rejects_missing_key(self):
        with self.assertRaises(ValueError):
            factor.validate_input({"seat_rank": pd.DataFrame()})

    def test_rejects_empty(self):
        frames = load_fixture()
        frames["net_margin"] = frames["net_margin"].iloc[0:0]
        with self.assertRaises(ValueError):
            factor.validate_input(frames)

    def test_rejects_missing_columns(self):
        frames = load_fixture()
        frames["seat_rank"] = frames["seat_rank"].drop(columns=["net_position_change"])
        with self.assertRaises(ValueError):
            factor.validate_input(frames)


class FactorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = load_fixture()
        cls.panel = factor.run(cls.frames)

    def test_columns(self):
        self.assertEqual(
            list(self.panel.columns),
            ["date", "product", "f1", "f1_5d", "f5", "f6", "f8", "seat"])

    def test_no_duplicate_keys(self):
        self.assertEqual(self.panel.duplicated(["date", "product"]).sum(), 0)

    def test_seat_is_finite(self):
        seat = self.panel["seat"].dropna()
        self.assertGreater(len(seat), 100)
        self.assertTrue(np.isfinite(seat).all())

    def test_no_future_data(self):
        dates = sorted(self.panel["date"].unique())
        d = dates[int(len(dates) * 0.8)]
        part = factor.run({
            "seat_rank": self.frames["seat_rank"][self.frames["seat_rank"]["date"] <= d],
            "net_margin": self.frames["net_margin"][self.frames["net_margin"]["date"] <= d],
        })
        left = self.panel[self.panel["date"] == d].set_index("product")
        right = part[part["date"] == d].set_index("product")
        common = left.index.intersection(right.index)
        self.assertGreater(len(common), 0)
        for col in ("f1", "f5", "f6", "f8", "seat"):
            a = left.loc[common, col]
            b = right.loc[common, col]
            mask = a.notna() & b.notna()
            if mask.any():
                self.assertLess(float((a[mask] - b[mask]).abs().max()), 1e-9)


class BacktestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = factor.run(load_fixture())
        cls.baseline = data_layer.load_baseline()
        cls.result = backtest.run({"panel": cls.panel, **cls.baseline},
                                  {"top_k": 1, "min_products": 2})

    def test_metrics_include_seat_and_cta(self):
        names = {row["strategy"] for row in self.result["metrics"]}
        self.assertIn("seat", names)
        self.assertIn("cta", names)

    def test_equity_not_empty(self):
        self.assertGreater(len(self.result["equity"]["seat"]), 20)

    def test_metrics_numeric(self):
        for row in self.result["metrics"]:
            self.assertIsInstance(row["annual_return"], float)
            self.assertIsInstance(row["max_drawdown"], float)


class ProductionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = factor.run(load_fixture())
        cls.frame = production.to_production(cls.panel, "test-version")

    def test_schema(self):
        required = {"trade_date", "asset_type", "symbol", "factor_id", "factor_name",
                    "factor_value", "score", "rank", "signal", "confidence",
                    "data_version", "update_time"}
        self.assertEqual(set(self.frame.columns), required)

    def test_signal_enum(self):
        self.assertTrue(set(self.frame["signal"].unique()) <= {"buy", "hold", "sell"})

    def test_primary_key(self):
        self.assertEqual(
            self.frame.duplicated(["trade_date", "symbol", "factor_id"]).sum(), 0)

    def test_top_k(self):
        counts = self.frame[self.frame["signal"] == "buy"].groupby("trade_date").size()
        self.assertLessEqual(int(counts.max()), production.TOP_K)


if __name__ == "__main__":
    unittest.main(verbosity=2)
