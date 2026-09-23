"""Tests: parameter validation (never raises on bad input)."""
import unittest

from core.validation import (validate_config, has_errors, worst_severity,
                             validate_time, ERROR, WARNING, INFO)
from tests import std_ctx


class TestValidationRules(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def codes(self, issues):
        return {i.code for i in issues}

    def test_valid_default_config_has_no_errors(self):
        issues = validate_config(self.cfg, self.prof, self.acct, 500.0)
        self.assertFalse(has_errors(issues))
        # default does carry the documented INFO that emergency brake is off
        self.assertIn("EMERGENCY_OFF", self.codes(issues))

    def test_grid_step_must_be_positive(self):
        self.cfg.GridStepUSD = 0
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("GRID_STEP_POSITIVE", self.codes(issues))

    def test_multiplier_and_baselot(self):
        self.cfg.LotMultiplier = 0
        self.cfg.BaseLot = -1
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("MULTIPLIER_POSITIVE", self.codes(issues))
        self.assertIn("BASELOT_POSITIVE", self.codes(issues))

    def test_basket_target_negative(self):
        self.cfg.BasketCloseAllUSD = -0.1
        self.assertIn("BASKET_TARGET_NON_NEGATIVE",
                      self.codes(validate_config(self.cfg, self.prof, self.acct)))

    def test_partial_percent_range(self):
        self.cfg.ProfitPartialPercent = 150
        self.assertIn("PARTIAL_PERCENT_RANGE",
                      self.codes(validate_config(self.cfg, self.prof, self.acct)))
        self.cfg.ProfitPartialPercent = -5
        self.assertIn("PARTIAL_PERCENT_RANGE",
                      self.codes(validate_config(self.cfg, self.prof, self.acct)))

    def test_time_format(self):
        self.cfg.FridayCloseAllThaiTime = "25:00"
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("TIME_FORMAT", self.codes(issues))
        self.assertTrue(validate_time("08:00"))
        self.assertTrue(validate_time("17:59"))
        self.assertFalse(validate_time("8:00"))
        self.assertFalse(validate_time("08:60"))
        self.assertFalse(validate_time(""))

    def test_lot_constraints(self):
        self.cfg.BaseLot = 0.001   # below min 0.01
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("BASELOT_BELOW_MIN", self.codes(issues))
        self.cfg.BaseLot = 200     # above max 100
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("BASELOT_ABOVE_MAX", self.codes(issues))
        self.cfg.BaseLot = 0.015   # not on 0.01 step
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("BASELOT_NOT_ON_STEP", self.codes(issues))

    def test_partial_never_fires_warning(self):
        # default: trigger 2.0 > basket 1.68
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("PARTIAL_NEVER_FIRES", self.codes(issues))

    def test_trailing_lock_above_start(self):
        self.cfg.UseMainSideTrailing = True
        self.cfg.MainTrailLockUSD = 5.0
        self.assertIn("TRAIL_LOCK_ABOVE_START",
                      self.codes(validate_config(self.cfg, self.prof, self.acct)))

    def test_no_grid_side(self):
        self.cfg.UseGridBuy = False
        self.cfg.UseGridSell = False
        self.assertIn("NO_GRID_SIDE",
                      self.codes(validate_config(self.cfg, self.prof, self.acct)))

    def test_extreme_multiplier(self):
        self.cfg.LotMultiplier = 2.5
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("EXTREME_MULTIPLIER", self.codes(issues))

    def test_insufficient_capital(self):
        # first order margin at 2000 ref price: 0.1*100*2000/500 = 40
        issues = validate_config(self.cfg, self.prof, self.acct, capital=30.0)
        self.assertIn("INSUFFICIENT_CAPITAL", self.codes(issues))
        self.assertTrue(has_errors(issues))

    def test_invalid_leverage_and_contract(self):
        self.acct.leverage = 0
        self.prof.contract_size = 0
        issues = validate_config(self.cfg, self.prof, self.acct)
        self.assertIn("LEVERAGE_POSITIVE", self.codes(issues))
        self.assertIn("CONTRACT_SIZE_POSITIVE", self.codes(issues))

    def test_never_raises_on_garbage(self):
        bad = self.cfg
        bad.GridStepUSD = float("nan")
        try:
            issues = validate_config(bad, self.prof, self.acct, 0.0)
            self.assertIsInstance(issues, list)
        except Exception as exc:  # pragma: no cover
            self.fail(f"validation raised on NaN input: {exc}")

    def test_severity_helpers(self):
        issues = validate_config(self.cfg, self.prof, self.acct, 500.0)
        self.assertEqual(worst_severity([]), INFO)
        self.assertEqual(worst_severity(issues), WARNING)
        self.assertEqual(worst_severity(validate_config(
            self.cfg, self.prof, self.acct, 1.0)), ERROR)


if __name__ == "__main__":
    unittest.main()
