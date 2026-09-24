"""Tests: grid calculator (Module 2)."""
import unittest

from core.grid import build_grid_table
from core import calculations as c
from tests import std_ctx


class TestGridTable(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_table_structure_buy(self):
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 5, "BUY")
        self.assertEqual(len(t.rows), 5)
        self.assertEqual(t.rows[0].level, 1)
        self.assertEqual(t.rows[0].entry_price, 2000.0)
        self.assertEqual(t.rows[4].entry_price, 1980.0)
        self.assertEqual([r.lot for r in t.rows], [0.1, 0.11, 0.12, 0.13, 0.14])
        self.assertEqual(t.rows[-1].cumulative_lot, 0.60)
        self.assertAlmostEqual(t.total_margin, c.margin_used(0.60, 2000.0, self.prof, self.acct))

    def test_floating_pl_at_open_negative(self):
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 3, "BUY")
        # at level 3 open (1990): L1 -100, L2 -55, L3 0 -> -155
        self.assertAlmostEqual(t.rows[2].floating_pl_at_open, -155.0)
        # level 1 open: position just opened at 2000 -> 0
        self.assertAlmostEqual(t.rows[0].floating_pl_at_open, 0.0)

    def test_sell_side_mirrors(self):
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 3, "SELL")
        self.assertEqual(t.rows[2].entry_price, 2010.0)
        self.assertAlmostEqual(t.rows[2].floating_pl_at_open, -155.0)

    def test_disabled_side_returns_empty(self):
        self.cfg.UseGridBuy = False
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 5, "BUY")
        self.assertEqual(t.rows, [])
        self.assertEqual(t.total_lot, 0.0)

    def test_assumptions_attached(self):
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 2, "BUY")
        for aid in ("LOT_FORMULA_ASSUMPTION_001", "MARGIN_ASSUMPTION_001",
                    "PL_CONVERSION_ASSUMPTION_001"):
            self.assertIn(aid, t.assumptions)

    def test_levels_must_be_positive(self):
        with self.assertRaises(ValueError):
            build_grid_table(self.cfg, self.prof, self.acct, self.rules, 0, "BUY")

    def test_to_dicts_roundtrip_shape(self):
        t = build_grid_table(self.cfg, self.prof, self.acct, self.rules, 2, "BUY")
        rows = t.to_dicts()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["level"], 1)
        self.assertIn("cumulative_lot", rows[0])


if __name__ == "__main__":
    unittest.main()
