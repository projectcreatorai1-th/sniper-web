"""Tests: Assumption Registry (Module 11)."""
import json
import os
import unittest

from core.assumptions import (AssumptionRegistry, default_registry,
                              reset_default_registry, VERIFIED_FROM_DOCUMENTATION,
                              OBSERVED_FROM_TESTING, MODEL_ASSUMPTION, UNKNOWN,
                              ALL_STATUSES)
from tests import TempDirTestMixin


class TestAssumptionRegistry(TempDirTestMixin, unittest.TestCase):
    def test_registry_has_core_ids(self):
        reg = AssumptionRegistry()
        self.assertIsNotNone(reg.try_get("LOT_FORMULA_ASSUMPTION_001"))
        self.assertEqual(reg.status_of("LOT_FORMULA_ASSUMPTION_001"), MODEL_ASSUMPTION)
        self.assertEqual(reg.status_of("GRID_DISTANCE_DOC_001"),
                         VERIFIED_FROM_DOCUMENTATION)
        self.assertEqual(reg.status_of("BASKET_CLOSE_DOC_001"),
                         VERIFIED_FROM_DOCUMENTATION)
        self.assertEqual(reg.status_of("MAX_GRID_DEPTH_UNKNOWN_001"), UNKNOWN)

    def test_unknown_id_raises(self):
        reg = AssumptionRegistry()
        with self.assertRaises(KeyError):
            reg.get("NOPE_999")

    def test_status_change_and_persistence(self):
        path = os.path.join(self.tmpdir, "assumptions_overrides.json")
        reg = AssumptionRegistry(path)
        reg.set_status("GRID_TRIGGER_ASSUMPTION_001", OBSERVED_FROM_TESTING,
                       evidence="demo run 2026-09-23: adds measured from last order")
        self.assertEqual(reg.status_of("GRID_TRIGGER_ASSUMPTION_001"),
                         OBSERVED_FROM_TESTING)
        # reload from disk -> override survives
        reg2 = AssumptionRegistry(path)
        self.assertEqual(reg2.status_of("GRID_TRIGGER_ASSUMPTION_001"),
                         OBSERVED_FROM_TESTING)
        a = reg2.get("GRID_TRIGGER_ASSUMPTION_001")
        self.assertIn("demo run", a.evidence)

    def test_invalid_status_rejected(self):
        reg = AssumptionRegistry(os.path.join(self.tmpdir, "o.json"))
        with self.assertRaises(ValueError):
            reg.set_status("GRID_TRIGGER_ASSUMPTION_001", "MAYBE")

    def test_by_status_and_describe(self):
        reg = AssumptionRegistry()
        verified = reg.by_status(VERIFIED_FROM_DOCUMENTATION)
        self.assertGreater(len(verified), 3)
        desc = reg.describe(["LOT_FORMULA_ASSUMPTION_001", "MAX_GRID_DEPTH_UNKNOWN_001"])
        self.assertEqual(len(desc), 2)
        self.assertEqual(desc[0]["status"], MODEL_ASSUMPTION)

    def test_default_registry_singleton_resets(self):
        reset_default_registry()
        reg = default_registry()
        self.assertIsInstance(reg, AssumptionRegistry)
        reset_default_registry()

    def test_all_statuses_defined(self):
        self.assertEqual(ALL_STATUSES, (VERIFIED_FROM_DOCUMENTATION,
                                        OBSERVED_FROM_TESTING,
                                        MODEL_ASSUMPTION, UNKNOWN))


if __name__ == "__main__":
    unittest.main()
