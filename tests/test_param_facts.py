"""Tests: parameter facts — Emergency 90/50 separation + PARAM_21 UNKNOWN."""
import unittest

from core.config import EAConfig, builtin_presets
from core.param_facts import (
    DOCUMENTED,
    EA_DEFAULT,
    OBSERVED,
    OBSERVED_VALUE,
    RECOMMENDED_PRESET,
    UNVERIFIED_CANDIDATE,
    UNKNOWN,
    find_fact,
    parameter_21_fact,
    parameter_facts,
)


class TestEmergencyDistanceValues(unittest.TestCase):
    def test_observed_90_and_preset_50_are_separate_records(self):
        f = find_fact("PARAM_18")
        kinds = {v.kind: v.value for v in f.value_records}
        self.assertEqual(kinds[OBSERVED_VALUE], 90.0)
        self.assertEqual(kinds[RECOMMENDED_PRESET], 50.0)
        self.assertEqual(kinds[EA_DEFAULT], 50.0)
        self.assertNotEqual(kinds[OBSERVED_VALUE], kinds[RECOMMENDED_PRESET])

    def test_statuses(self):
        f = find_fact("PARAM_18")
        by_kind = {v.kind: v for v in f.value_records}
        self.assertEqual(by_kind[OBSERVED_VALUE].status, OBSERVED)
        self.assertEqual(by_kind[RECOMMENDED_PRESET].status, DOCUMENTED)
        self.assertEqual(by_kind[EA_DEFAULT].status, "MODEL")

    def test_model_default_unchanged_at_50(self):
        """Regression guard: EAConfig default and $500 preset stay at 50.0."""
        self.assertEqual(EAConfig().EmergencyDistanceFromCycleUSD, 50.0)
        p500 = builtin_presets()["Seller preset - Capital $500"]
        self.assertEqual(p500.EmergencyDistanceFromCycleUSD, 50.0)

    def test_sources_traceable(self):
        f = find_fact("PARAM_18")
        by_kind = {v.kind: v for v in f.value_records}
        self.assertIn("Installation Video", by_kind[OBSERVED_VALUE].source)
        self.assertEqual(by_kind[OBSERVED_VALUE].evidence_id, "E007")
        self.assertEqual(by_kind[RECOMMENDED_PRESET].evidence_id, "E008")

    def test_no_best_value_claim(self):
        f = find_fact("PARAM_18")
        joined = f.notes.lower()
        self.assertNotIn("best", joined)
        self.assertNotIn("ดีที่สุด", f.notes)


class TestParameter21(unittest.TestCase):
    def test_remains_unknown(self):
        f = parameter_21_fact()
        self.assertEqual(f.status, UNKNOWN)
        self.assertEqual(f.meaning, UNKNOWN)
        self.assertEqual(f.evidence_ids, [])
        self.assertEqual(f.value_records, [])

    def test_candidate_name_is_unverified(self):
        f = parameter_21_fact()
        self.assertEqual(f.code_name, "AccumTargetUSD")
        self.assertIn(UNVERIFIED_CANDIDATE, f.notes)

    def test_not_marked_verified(self):
        f = parameter_21_fact()
        self.assertNotEqual(f.status, DOCUMENTED)
        self.assertNotEqual(f.status, OBSERVED)

    def test_registry_contains_both_facts(self):
        ids = {f.parameter_id for f in parameter_facts()}
        self.assertIn("PARAM_18", ids)
        self.assertIn("PARAM_21", ids)


if __name__ == "__main__":
    unittest.main()
