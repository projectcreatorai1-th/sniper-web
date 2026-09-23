"""Tests: single-source-of-truth calculations."""
import unittest

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules, LOT_ARITHMETIC_STEP, LOT_FLAT
from core.symbol_profile import SymbolProfile, AccountSettings
from tests import std_ctx


class TestNormalizeLot(unittest.TestCase):
    def setUp(self):
        self.prof = SymbolProfile()          # lot_step 0.01

    def test_rounds_to_step(self):
        self.assertEqual(c.normalize_lot(0.111, self.prof), 0.11)
        self.assertEqual(c.normalize_lot(0.116, self.prof), 0.12)
        self.assertEqual(c.normalize_lot(0.1, self.prof), 0.1)

    def test_zero_step_passthrough(self):
        self.prof.lot_step = 0.0
        self.assertAlmostEqual(c.normalize_lot(0.123456, self.prof), 0.123456)

    def test_no_silent_clamping(self):
        # below lot_min stays as-is (validation warns instead) - honest model
        self.prof.lot_min = 0.1
        self.assertEqual(c.normalize_lot(0.02, self.prof), 0.02)


class TestLotFormula(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_geometric_progression(self):
        lots = [c.lot_for_level(self.cfg, i, self.rules, self.prof).value
                for i in range(1, 6)]
        self.assertEqual(lots, [0.1, 0.11, 0.12, 0.13, 0.15])

    def test_optimization_off_is_flat(self):
        self.cfg.UsePositionSizeOptimization = False
        for i in (1, 2, 7):
            self.assertEqual(c.lot_for_level(self.cfg, i, self.rules, self.prof).value, 0.1)

    def test_arithmetic_rule_variant(self):
        self.rules.lot_formula = LOT_ARITHMETIC_STEP
        self.rules.arithmetic_step_lots = 0.05
        self.assertEqual(c.lot_for_level(self.cfg, 3, self.rules, self.prof).value, 0.2)

    def test_flat_rule_variant(self):
        self.rules.lot_formula = LOT_FLAT
        self.assertEqual(c.lot_for_level(self.cfg, 9, self.rules, self.prof).value, 0.1)

    def test_level_must_be_positive(self):
        with self.assertRaises(ValueError):
            c.raw_lot_for_level(self.cfg, 0, self.rules)

    def test_assumptions_attached(self):
        res = c.lot_for_level(self.cfg, 2, self.rules, self.prof)
        self.assertIn("LOT_FORMULA_ASSUMPTION_001", res.assumptions)

    def test_lots_for_levels_and_cumulative(self):
        lots, assumptions = c.lots_for_levels(self.cfg, 3, self.rules, self.prof)
        self.assertEqual(lots, [0.1, 0.11, 0.12])
        self.assertEqual(c.cumulative_lots(lots), [0.1, 0.21, 0.33])


class TestGridGeometry(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_buy_grid_adds_down_sell_up(self):
        self.assertEqual(c.entry_price_for_level(2000.0, 1, "BUY", 5.0), 2000.0)
        self.assertEqual(c.entry_price_for_level(2000.0, 3, "BUY", 5.0), 1990.0)
        self.assertEqual(c.entry_price_for_level(2000.0, 3, "SELL", 5.0), 2010.0)

    def test_levels_for_adverse_move(self):
        self.assertEqual(c.levels_for_adverse_move(0.0, 5.0), 1)
        self.assertEqual(c.levels_for_adverse_move(4.99, 5.0), 1)
        self.assertEqual(c.levels_for_adverse_move(5.0, 5.0), 2)
        self.assertEqual(c.levels_for_adverse_move(49.9, 5.0), 10)
        self.assertEqual(c.levels_for_adverse_move(50.0, 5.0), 11)

    def test_invalid_move_raises(self):
        with self.assertRaises(ValueError):
            c.levels_for_adverse_move(-1, 5.0)
        with self.assertRaises(ValueError):
            c.levels_for_adverse_move(10, 0.0)


class TestPLAndMargin(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_position_pl_buy_sell(self):
        # XAUUSD cs=100: 0.1 lot -> $10 per $1 move
        self.assertAlmostEqual(c.position_pl("BUY", 2000, 2001, 0.1, self.prof), 10.0)
        self.assertAlmostEqual(c.position_pl("SELL", 2000, 2001, 0.1, self.prof), -10.0)
        self.assertAlmostEqual(c.position_pl("BUY", 2000, 1995, 0.1, self.prof), -50.0)

    def test_basket_pl_sums_positions(self):
        positions = [("BUY", 2000.0, 0.1), ("BUY", 1995.0, 0.11)]
        # at 1995: -50 + 0 = -50
        self.assertAlmostEqual(c.basket_pl(positions, 1995.0, self.prof), -50.0)

    def test_notional_exposure(self):
        self.assertAlmostEqual(c.notional_exposure(0.1, 2000.0, self.prof), 20000.0)

    def test_margin_used(self):
        # 0.1 x 100 x 2000 / 500 = 40
        self.assertAlmostEqual(
            c.margin_used(0.1, 2000.0, self.prof, self.acct), 40.0)
        self.acct.margin_rate = 2.0
        self.assertAlmostEqual(
            c.margin_used(0.1, 2000.0, self.prof, self.acct), 80.0)

    def test_margin_level_and_dd(self):
        self.assertAlmostEqual(c.drawdown_percent(-250.0, 500.0), 50.0)
        self.assertAlmostEqual(c.drawdown_percent(10.0, 500.0), 0.0)  # profits don't make DD
        self.assertAlmostEqual(c.margin_level_percent(500.0, 250.0), 200.0)
        self.assertIsNone(c.margin_level_percent(500.0, 0.0))

    def test_weighted_average_entry(self):
        positions = [("BUY", 2000.0, 0.1), ("BUY", 1990.0, 0.3)]
        self.assertAlmostEqual(c.weighted_average_entry(positions), 1992.5)
        self.assertIsNone(c.weighted_average_entry([]))


class TestBasketMath(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_price_move_for_target(self):
        # total 0.1 lot -> sensitivity 10 $/($1); from -50 to +1.68 needs 5.168
        move = c.price_move_for_basket_target(-50.0, 0.1, 1.68, self.prof)
        self.assertAlmostEqual(move, 5.168, places=4)

    def test_price_move_zero_lots_returns_none(self):
        self.assertIsNone(c.price_move_for_basket_target(0.0, 0.0, 1.68, self.prof))

    def test_partial_close_volume(self):
        self.assertAlmostEqual(c.partial_close_volume(0.5, 50.0, self.prof), 0.25)

    def test_partial_close_realized_pro_rata(self):
        self.assertAlmostEqual(
            c.partial_close_realized_pl(2.0, 50.0, "PRO_RATA_VOLUME"), 1.0)

    def test_build_side_positions(self):
        positions, assumptions = c.build_side_positions(
            self.cfg, "BUY", 2000.0, 3, self.rules, self.prof)
        self.assertEqual(len(positions), 3)
        self.assertEqual(positions[0], ("BUY", 2000.0, 0.1))
        self.assertIn("GRID_DIRECTION_ASSUMPTION_001", assumptions)

    def test_build_side_positions_disabled_side(self):
        self.cfg.UseGridSell = False
        positions, _ = c.build_side_positions(
            self.cfg, "SELL", 2000.0, 3, self.rules, self.prof)
        self.assertEqual(positions, [])


if __name__ == "__main__":
    unittest.main()
