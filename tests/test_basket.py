"""Tests: basket / partial close simulation (Module 4)."""
import unittest

from core.basket import simulate_basket
from tests import std_ctx


class TestBasketSim(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_basket_at_depth_5(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 5)
        self.assertAlmostEqual(b.total_lots, 0.60)
        self.assertAlmostEqual(b.current_basket_pl, -550.0)   # deepest point
        self.assertEqual(b.partial_trigger, 2.0)
        self.assertEqual(b.basket_target, 1.68)
        self.assertAlmostEqual(b.partial_close_volume, 0.3)   # 50% of 0.60 -> 0.30

    def test_price_move_to_target(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 5)
        # (1.68 + 550) / (0.60 * 100) = 9.194666... (floor ladder, MC-001)
        self.assertAlmostEqual(b.price_move_to_target, 9.19466667, places=6)

    def test_price_move_to_partial_trigger(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 5)
        self.assertAlmostEqual(b.price_move_to_partial, 9.2, places=6)

    def test_partial_realized_pro_rata(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 5)
        # realizes 50% of the trigger value at trigger time
        self.assertAlmostEqual(b.partial_realized_pl, 1.0)

    def test_partial_disabled(self):
        self.cfg.UseProfitPartialClose = False
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 3)
        self.assertIsNone(b.partial_trigger)
        self.assertEqual(b.partial_close_volume, 0.0)
        self.assertAlmostEqual(b.partial_remaining_lots, b.total_lots)

    def test_basket_close_disabled(self):
        self.cfg.UseBasketCloseAll = False
        b = simulate_basket(self.cfg, self.prof, self.rules, "SELL", 3)
        self.assertIsNone(b.basket_target)
        self.assertIsNone(b.price_move_to_target)

    def test_only_once_flag(self):
        b1 = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 3,
                             partial_already_done=False)
        self.assertTrue(b1.partial_pending)
        self.cfg.ProfitPartialOnlyOnce = False
        b2 = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 3,
                             partial_already_done=True)
        self.assertTrue(b2.partial_pending)

    def test_current_price_override(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 3,
                            current_price=2001.0)
        # L1: +10, L2: +60*... L2 entry 1995 at 2001: +66, L3 entry 1990: +132
        self.assertAlmostEqual(b.current_basket_pl, 10 + 66 + 132)

    def test_assumptions_attached(self):
        b = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 2)
        for aid in ("BASKET_CLOSE_DOC_001", "PARTIAL_CLOSE_ASSUMPTION_001"):
            self.assertIn(aid, b.assumptions)

    def test_invalid_depth(self):
        with self.assertRaises(ValueError):
            simulate_basket(self.cfg, self.prof, self.rules, "BUY", 0)


if __name__ == "__main__":
    unittest.main()
