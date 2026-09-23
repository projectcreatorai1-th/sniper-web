"""Tests: EA config model, defaults, presets, round-trips (Module 1)."""
import unittest

from core.config import EAConfig, SCHEMA, builtin_presets
from tests import std_ctx


class TestEAConfig(unittest.TestCase):
    def test_default_values(self):
        cfg = EAConfig()
        self.assertEqual(cfg.TradeSymbol, "")
        self.assertTrue(cfg.UseGridBuy)
        self.assertTrue(cfg.UseGridSell)
        self.assertEqual(cfg.GridStepUSD, 5.0)
        self.assertEqual(cfg.BaseLot, 0.1)
        self.assertTrue(cfg.UsePositionSizeOptimization)
        self.assertEqual(cfg.LotMultiplier, 1.1)
        self.assertTrue(cfg.UseBasketCloseAll)
        self.assertEqual(cfg.BasketCloseAllUSD, 1.68)
        self.assertFalse(cfg.UseMainSideTrailing)
        self.assertEqual(cfg.MainTrailStartProfitUSD, 3.0)
        self.assertEqual(cfg.MainTrailLockUSD, 1.5)
        self.assertTrue(cfg.UseProfitPartialClose)
        self.assertEqual(cfg.ProfitPartialTriggerUSD, 2.0)
        self.assertEqual(cfg.ProfitPartialPercent, 50.0)
        self.assertTrue(cfg.ProfitPartialOnlyOnce)
        self.assertFalse(cfg.EnableEmergencyStop)
        self.assertEqual(cfg.EmergencyDistanceFromCycleUSD, 50.0)
        self.assertFalse(cfg.EmergencyCloseAllWhenTriggered)
        self.assertEqual(cfg.DailyResumeThaiTimeAfterEmergency, "08:00")
        self.assertEqual(cfg.AccumTargetUSD, 0.0)
        self.assertFalse(cfg.EnablePauseAfterAccumTargetHit)
        self.assertEqual(cfg.ResumeNextDayThaiTimeAfterTarget, "08:00")
        self.assertFalse(cfg.EnableFridayHardStop)
        self.assertFalse(cfg.FridayCloseAllAtTime)
        self.assertEqual(cfg.FridayCloseAllThaiTime, "17:00")
        self.assertEqual(cfg.MondayRestartThaiTime, "08:00")

    def test_parameter_count_is_27(self):
        self.assertEqual(len(EAConfig.parameter_meta()), 27)
        self.assertEqual(EAConfig().parameter_count(), 27)

    def test_to_from_dict_roundtrip(self):
        cfg = EAConfig()
        cfg.GridStepUSD = 7.7
        cfg.UseGridSell = False
        cfg.FridayCloseAllThaiTime = "16:30"
        d = cfg.to_dict()
        self.assertEqual(d["schema"], SCHEMA)
        restored = EAConfig.from_dict(d)
        self.assertEqual(restored.GridStepUSD, 7.7)
        self.assertFalse(restored.UseGridSell)
        self.assertEqual(restored.FridayCloseAllThaiTime, "16:30")

    def test_from_dict_tolerates_unknown_and_string_bools(self):
        cfg = EAConfig.from_dict({"GridStepUSD": "9.5", "UseGridBuy": "false",
                                  "NotAParam": 123})
        self.assertEqual(cfg.GridStepUSD, 9.5)
        self.assertFalse(cfg.UseGridBuy)

    def test_copy_is_deep(self):
        cfg = EAConfig()
        cp = cfg.copy()
        cp.BaseLot = 5.0
        self.assertEqual(cfg.BaseLot, 0.1)


class TestPresets(unittest.TestCase):
    def test_builtin_presets_exist(self):
        presets = builtin_presets()
        self.assertIn("Default (PDF manual V1.68)", presets)
        self.assertIn("Seller preset - Capital $500", presets)
        self.assertIn("Seller preset - Capital $3000", presets)

    def test_preset_500_equals_defaults(self):
        # verified from the $500 infographic: identical to manual defaults
        self.assertEqual(builtin_presets()["Seller preset - Capital $500"].to_dict(),
                         EAConfig().to_dict())

    def test_preset_3000_values(self):
        # verified from the $3000 infographic
        cfg = builtin_presets()["Seller preset - Capital $3000"]
        self.assertEqual(cfg.GridStepUSD, 4.8)
        self.assertEqual(cfg.BaseLot, 0.18)
        self.assertEqual(cfg.LotMultiplier, 1.08)
        self.assertEqual(cfg.BasketCloseAllUSD, 8.88)
        self.assertEqual(cfg.ProfitPartialTriggerUSD, 1.0)
        self.assertEqual(cfg.FridayCloseAllThaiTime, "08:00")

    def test_no_safety_wording_in_preset_names(self):
        for name in builtin_presets():
            low = name.lower()
            self.assertNotIn("safe", low)
            self.assertNotIn("best", low)


if __name__ == "__main__":
    unittest.main()
