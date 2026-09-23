"""Tests: backtest analyzer (Module 7)."""
import unittest

from core.backtest_analysis import analyze_backtest
from core.backtest_io import BacktestSummary, DealRecord
from tests import TempDirTestMixin


def _deals() -> list:
    """buy grid 3 deep then close, then a losing cycle then recovery."""
    rows = [
        ("2024.01.02 09:00:00", "balance", "", 0.0, 0.0, 0.0, 5000.0),
        ("2024.01.02 09:00:01", "buy", "in", 0.10, 2050.0, 0.0, 5000.0),
        ("2024.01.02 09:30:00", "buy", "in", 0.11, 2045.0, 0.0, 5000.0),
        ("2024.01.02 10:00:00", "buy", "in", 0.12, 2040.0, 0.0, 5000.0),
        ("2024.01.02 12:00:00", "buy", "out", 0.33, 2046.0, 60.0, 5060.0),
        ("2024.01.03 09:00:00", "buy", "in", 0.10, 2040.0, 0.0, 5060.0),
        ("2024.01.03 12:00:00", "buy", "out", 0.10, 2035.0, -50.0, 5010.0),
        ("2024.01.04 09:00:00", "buy", "in", 0.10, 2036.0, 0.0, 5010.0),
        ("2024.01.04 12:00:00", "buy", "out", 0.10, 2040.0, 40.0, 5050.0),
    ]
    return [DealRecord(time=t, symbol="XAUUSD", type=ty, direction=d, volume=v,
                       price=p, commission=0.0, swap=0.0, profit=pr, balance=b)
            for (t, ty, d, v, p, pr, b) in rows]


class TestAnalyzer(unittest.TestCase):
    def test_grid_depth_tracking(self):
        s = BacktestSummary(deals=_deals())
        a = analyze_backtest(s)
        self.assertTrue(a.has_deal_data)
        self.assertEqual(a.max_grid_depth_total, 3)
        self.assertEqual(a.max_grid_depth_buy, 3)
        self.assertEqual(a.max_grid_depth_sell, 0)
        self.assertEqual(a.entry_deals, 5)
        self.assertEqual(a.exit_deals, 3)   # last tuple field unused, exits=3

    def test_lot_statistics(self):
        s = BacktestSummary(deals=_deals())
        a = analyze_backtest(s)
        self.assertAlmostEqual(a.max_lot, 0.12)
        self.assertAlmostEqual(a.avg_lot, round((0.1 + 0.11 + 0.12 + 0.1 + 0.1) / 5, 4))
        self.assertAlmostEqual(a.total_volume, 0.53)

    def test_drawdown_episode(self):
        s = BacktestSummary(deals=_deals())
        a = analyze_backtest(s)
        ep = a.max_drawdown_episode
        self.assertIsNotNone(ep)
        self.assertAlmostEqual(ep.peak_balance, 5060.0)
        self.assertAlmostEqual(ep.trough_balance, 5010.0)
        self.assertAlmostEqual(ep.depth, 50.0)
        # not recovered before the report ends -> recovery_time stays None
        self.assertIsNone(ep.recovery_time)
        # longest recovery episode is the same single episode here
        self.assertEqual(a.longest_recovery_episode.depth, 50.0)

    def test_losing_streak(self):
        s = BacktestSummary(deals=_deals())
        a = analyze_backtest(s)
        self.assertEqual(a.worst_losing_streak_deals, 1)
        self.assertAlmostEqual(a.worst_losing_streak_amount, -50.0)

    def test_balance_curve_extracted(self):
        s = BacktestSummary(deals=_deals())
        a = analyze_backtest(s)
        self.assertEqual(len(a.balance_curve), 9)
        self.assertEqual(a.balance_curve[0], 5000.0)

    def test_no_deal_data_notes(self):
        s = BacktestSummary(net_profit=100.0)
        a = analyze_backtest(s)
        self.assertFalse(a.has_deal_data)
        self.assertTrue(a.notes)
        self.assertIsNone(a.max_grid_depth_total)


if __name__ == "__main__":
    unittest.main()
