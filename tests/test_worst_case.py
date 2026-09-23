"""Tests: worst case simulator (Module 3)."""
import unittest

from core.worst_case import (simulate_worst_case, simulate_moves,
                             BUY_ADVERSE, SELL_ADVERSE, BOTH_SIDES)
from tests import std_ctx


class TestWorstCase(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_buy_adverse_levels_and_pl(self):
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 10.0, BUY_ADVERSE)
        # move 10 / step 5 -> 3 levels (2000, 1995, 1990), price ends 1990
        self.assertEqual(r.grid_levels, 3)
        self.assertAlmostEqual(r.total_lots, 0.33)
        # L1: -10*0.1*100=-100 ; L2: -5*0.11*100=-55 ; L3: 0
        self.assertAlmostEqual(r.floating_pl, -155.0)
        self.assertAlmostEqual(r.equity, 345.0)
        self.assertAlmostEqual(r.drawdown_pct, 31.0, places=3)

    def test_sell_adverse_mirrors_buy(self):
        rb = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, 10.0, BUY_ADVERSE)
        rs = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, 10.0, SELL_ADVERSE)
        self.assertEqual(rs.grid_levels, rb.grid_levels)
        self.assertAlmostEqual(rs.floating_pl, rb.floating_pl)
        self.assertEqual(rs.end_price, 2010.0)

    def test_both_sides_hedge_offset(self):
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 10.0, BOTH_SIDES)
        # buy basket -155, sell L1 gains +100 (sell 2000 -> 1990)
        self.assertAlmostEqual(r.floating_pl, -55.0)
        # total lots include the sell hedge level 1
        self.assertAlmostEqual(r.total_lots, 0.43)

    def test_both_sides_without_sell_grid(self):
        self.cfg.UseGridSell = False
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 10.0, BOTH_SIDES)
        self.assertAlmostEqual(r.floating_pl, -155.0)

    def test_margin_level_present(self):
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 10.0, BUY_ADVERSE)
        self.assertIsNotNone(r.margin_level_pct)
        self.assertGreater(r.margin_level_pct, 100.0)

    def test_emergency_note_when_enabled(self):
        self.cfg.EnableEmergencyStop = True
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 60.0, BUY_ADVERSE)
        self.assertTrue(r.emergency_triggered)
        self.assertIn("Emergency", r.emergency_note)

    def test_emergency_not_triggered_below_distance(self):
        self.cfg.EnableEmergencyStop = True
        r = simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 50.0, BUY_ADVERSE)
        self.assertFalse(r.emergency_triggered)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError):
            simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                0.0, 10.0, BUY_ADVERSE)
        with self.assertRaises(ValueError):
            simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, -1.0, BUY_ADVERSE)
        with self.assertRaises(ValueError):
            simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                500.0, 10.0, "NOT_A_SCENARIO")

    def test_simulate_moves_matrix(self):
        results = simulate_moves(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, [10.0, 20.0])
        self.assertEqual(len(results), 6)   # 2 moves x 3 scenarios
        r = results[0].to_dict()
        self.assertIn("assumptions", r)
        self.assertIn("BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001",
                      results[2].assumptions)


if __name__ == "__main__":
    unittest.main()
