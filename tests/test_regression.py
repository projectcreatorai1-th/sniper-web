"""REGRESSION TESTS — pinned values for the reference example.

Baseline: BaseLot 0.1, LotMultiplier 1.1, GridStepUSD 5.0, XAUUSD profile
(contract 100, lot step 0.01, reference price 2000, leverage 1:500),
capital $500.

These values are hand-verified against the documented behavior
(0.1 lot XAUUSD moves ~$10 per $1 price move — Full Report section 6).
If one of these tests fails after a change, the calculation core changed
behavior INTENTIONALLY or NOT - find out which before updating the pins.
"""
import unittest

from core import calculations as c
from core.basket import simulate_basket
from core.grid import build_grid_table
from core.risk import build_risk_summary, RiskThresholds, FLAG_MODEL_ASSUMPTION, \
    FLAG_EA_BEHAVIOR_NOT_VERIFIED
from core.worst_case import simulate_worst_case, BUY_ADVERSE, SELL_ADVERSE, BOTH_SIDES
from tests import std_ctx


class TestRegressionBaseline(unittest.TestCase):
    """BaseLot 0.1 / Multiplier 1.1 / GridStep 5 — exact expected outputs."""

    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_lot_sequence(self):
        lots = [c.lot_for_level(self.cfg, i, self.rules, self.prof).value
                for i in range(1, 11)]
        self.assertEqual(lots, [0.1, 0.11, 0.12, 0.13, 0.14,
                                0.16, 0.17, 0.19, 0.21, 0.23])

    def test_cumulative_lots_5_levels(self):
        self.assertEqual(c.cumulative_lots([0.1, 0.11, 0.12, 0.13, 0.15]),
                         [0.1, 0.21, 0.33, 0.46, 0.61])

    def test_grid_table_level3_floating(self):
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 3, "BUY")
        self.assertAlmostEqual(t.rows[2].floating_pl_at_open, -155.0)
        self.assertAlmostEqual(t.rows[2].margin, 0.33 * 100 * 1990.0 / 500.0)

    def test_worst_case_10_buy(self):
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 10.0, BUY_ADVERSE)
        self.assertEqual(r.grid_levels, 3)
        self.assertAlmostEqual(r.total_lots, 0.33)
        self.assertAlmostEqual(r.floating_pl, -155.0)
        self.assertAlmostEqual(r.equity, 345.0)
        self.assertAlmostEqual(r.drawdown_pct, 31.0)

    def test_worst_case_50_both_sides(self):
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 50.0, BOTH_SIDES)
        self.assertEqual(r.grid_levels, 11)
        self.assertAlmostEqual(r.total_lots, 1.91)
        self.assertAlmostEqual(r.floating_pl, -3200.0)
        self.assertAlmostEqual(r.drawdown_pct, 640.0)

    def test_worst_case_50_sell_adverse_symmetry(self):
        rb = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, 50.0, BUY_ADVERSE)
        rs = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, 50.0, SELL_ADVERSE)
        self.assertEqual(rs.floating_pl, rb.floating_pl)
        self.assertEqual(rs.total_lots, rb.total_lots)

    def test_basket_target_move_level5(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 5)
        self.assertAlmostEqual(b.price_move_to_target, 9.19466667, places=6)
        self.assertAlmostEqual(b.partial_realized_pl, 1.0)
        self.assertAlmostEqual(b.partial_close_volume, 0.3)

    def test_first_order_margin(self):
        self.assertAlmostEqual(
            c.margin_used(0.1, 2000.0, self.prof, self.acct), 40.0)

    def test_documented_reference_check(self):
        """Full Report: 0.1 lot XAUUSD ≈ $10 per $1 move."""
        self.assertAlmostEqual(c.position_pl("BUY", 2000.0, 2001.0, 0.1, self.prof),
                               10.0)

    def test_risk_summary_flags_always_include_honesty_flags(self):
        s = build_risk_summary(self.cfg, self.prof, self.acct, self.rules,
                               500.0, RiskThresholds())
        flags = {f.flag for f in s.flags}
        self.assertIn(FLAG_MODEL_ASSUMPTION, flags)
        self.assertIn(FLAG_EA_BEHAVIOR_NOT_VERIFIED, flags)
        # $500 capital at a $50 gold move: DD far beyond capital
        self.assertGreater(s.estimated_dd_percent, 100.0)

    def test_preset_3000_regression(self):
        from core.config import builtin_presets
        cfg = builtin_presets()["Seller preset - Capital $3000"]
        lots = [c.lot_for_level(cfg, i, self.rules, self.prof).value
                for i in range(1, 4)]
        # floor ladder (MC-001): 0.18, floor(0.1944)=0.19, floor(0.209952)=0.20
        self.assertEqual(lots, [0.18, 0.19, 0.20])


if __name__ == "__main__":
    unittest.main()
