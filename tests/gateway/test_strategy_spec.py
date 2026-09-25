"""Strategy Specification tests — schema, integrity, status, determinism."""
import hashlib
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC_DIR = os.path.join(ROOT, "STRATEGY_SPEC")

STATUSES = {"VERIFIED", "PARTIAL", "UNKNOWN", "REJECTED", "HYPOTHESIS",
            "CONFIGURED", "DERIVED"}


def load(name):
    return json.load(open(os.path.join(SPEC_DIR, name), encoding="utf-8"))


class TestSpecFilesExist(unittest.TestCase):
    REQUIRED = ["strategy_spec.json", "parameter_spec.json",
                "state_transition_spec.json", "evidence_binding.json",
                "invariant_spec.json", "ea_build_contract.json",
                "spec_version.json", "decision_tree.md",
                "edge_case_matrix.md", "uncertainty_matrix.md",
                "signal_spec.md"]

    def test_all_files_present(self):
        for f in self.REQUIRED:
            self.assertTrue(os.path.exists(os.path.join(SPEC_DIR, f)),
                            f"missing: {f}")


class TestStrategySpec(unittest.TestCase):
    def setUp(self):
        self.spec = load("strategy_spec.json")

    def test_identity_present(self):
        ident = self.spec["spec_identity"]
        self.assertEqual(ident["spec_version"], "1.0.0")
        self.assertTrue(ident["evidence_model_hash"].startswith("124F"))

    def test_lot_model_verified(self):
        lot = self.spec["lot_model"]
        self.assertEqual(lot["base_lot"]["status"], "VERIFIED")
        self.assertEqual(lot["multiplier"]["status"], "VERIFIED")
        self.assertIn("FLOOR", lot["rounding"])

    def test_grid_trigger_partial(self):
        trigger = self.spec["grid_model"]["trigger_anchor"]
        self.assertEqual(trigger["status"], "PARTIAL")
        self.assertEqual(len(trigger["compatible_hypotheses"]), 2)

    def test_basket_trigger_partial_with_rejected(self):
        basket = self.spec["basket_model"]["close_trigger"]
        self.assertEqual(basket["status"], "PARTIAL")
        self.assertEqual(len(basket["compatible_hypotheses"]), 3)
        self.assertEqual(len(basket["rejected_hypotheses"]), 1)

    def test_partial_close_unknowns(self):
        pc = self.spec["partial_close_model"]
        self.assertEqual(pc["exists"]["status"], "VERIFIED")
        self.assertEqual(pc["trigger"]["status"], "UNKNOWN")
        self.assertEqual(pc["volume_rule"]["status"], "UNKNOWN")

    def test_emergency_unknown(self):
        em = self.spec["emergency_model"]["mechanism"]
        self.assertEqual(em["status"], "UNKNOWN")
        self.assertNotEqual(self.spec["emergency_model"]["our_ea_policy"]["source"],
                            "historical")

    def test_unknown_count(self):
        summary = self.spec["evidence_binding_summary"]
        self.assertEqual(summary["unknown"], 4)
        self.assertEqual(summary["verified"], 8)
        self.assertEqual(summary["partial"], 3)
        self.assertEqual(summary["rejected"], 1)

    def test_no_unknown_promoted(self):
        """Critical: UNKNOWN cannot silently become VERIFIED."""
        def check_status(node, path=""):
            if isinstance(node, dict):
                status = node.get("status")
                if status == "UNKNOWN":
                    # check no sibling field claims certainty
                    self.assertNotIn("value", node,
                                     f"UNKNOWN with value at {path}")
                for k, v in node.items():
                    check_status(v, f"{path}.{k}")
        check_status(self.spec)

    def test_rejected_not_in_compatible(self):
        """REJECTED hypothesis must not appear in compatible list."""
        basket = self.spec["basket_model"]["close_trigger"]
        compat_ids = [h["id"] for h in basket["compatible_hypotheses"]]
        rejected_ids = [h["id"] for h in basket["rejected_hypotheses"]]
        for rid in rejected_ids:
            self.assertNotIn(rid, compat_ids)


class TestParameterSpec(unittest.TestCase):
    def setUp(self):
        self.spec = load("parameter_spec.json")

    def test_all_parameters_have_required_fields(self):
        for p in self.spec["parameters"]:
            for field in ["parameter_id", "name", "type", "status",
                         "source"]:
                self.assertIn(field, p, f"missing {field} in {p}")

    def test_no_duplicate_parameter_ids(self):
        ids = [p["parameter_id"] for p in self.spec["parameters"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_lot_parameters_verified(self):
        by_id = {p["parameter_id"]: p for p in self.spec["parameters"]}
        self.assertEqual(by_id["PARAM-LOT-BASE"]["status"], "VERIFIED")
        self.assertEqual(by_id["PARAM-LOT-MULT"]["status"], "VERIFIED")
        self.assertEqual(by_id["PARAM-LOT-ROUNDING"]["value"], "FLOOR")

    def test_risk_parameters_configured_not_historical(self):
        by_id = {p["parameter_id"]: p for p in self.spec["parameters"]}
        for pid in ["PARAM-RISK-MAX-LOSS", "PARAM-RISK-MAX-DD"]:
            self.assertEqual(by_id[pid]["source"], "our_ea_policy")

    def test_hypothesis_parameters_partial(self):
        by_id = {p["parameter_id"]: p for p in self.spec["parameters"]}
        self.assertEqual(by_id["PARAM-GRID-ANCHOR"]["status"], "PARTIAL")
        self.assertEqual(by_id["PARAM-BASKET-TRIGGER"]["status"], "PARTIAL")


class TestStateTransitionSpec(unittest.TestCase):
    def setUp(self):
        self.spec = load("state_transition_spec.json")

    def test_17_states(self):
        self.assertEqual(self.spec["state_count"], 17)
        self.assertEqual(len(self.spec["states"]), 17)

    def test_transitions_have_from_event_to(self):
        for t in self.spec["transitions"]:
            self.assertIn("from", t)
            self.assertIn("event", t)
            self.assertIn("to", t)

    def test_all_states_in_transitions(self):
        used = set()
        for t in self.spec["transitions"]:
            used.add(t["from"])
            used.add(t["to"])
        for state in self.spec["states"]:
            self.assertIn(state, used, f"state {state} not in any transition")


class TestEvidenceBinding(unittest.TestCase):
    def setUp(self):
        self.spec = load("evidence_binding.json")

    def test_all_16_rules_bound(self):
        self.assertEqual(self.spec["total_rules"], 16)

    def test_all_chains_complete(self):
        self.assertEqual(self.spec["complete_chains"], 16)

    def test_verified_rules_have_evidence(self):
        for b in self.spec["bindings"]:
            if b["status"] == "VERIFIED":
                self.assertTrue(b["evidence_refs"],
                                f"VERIFIED rule {b['rule_id']} has no evidence")


class TestEABuildContract(unittest.TestCase):
    def setUp(self):
        self.spec = load("ea_build_contract.json")

    def test_ea_not_created(self):
        self.assertEqual(self.spec["ea_status"], "NOT_CREATED")

    def test_strategy_spec_hash_linked(self):
        self.assertTrue(self.spec["strategy_spec_hash"])

    def test_safety_requirements(self):
        safety = self.spec["safety_requirements"]
        self.assertTrue(any("LIVE" in s for s in safety))
        self.assertTrue(any("UNKNOWN" in s for s in safety))

    def test_test_requirements(self):
        tests = self.spec["test_requirements"]
        self.assertTrue(any("VERIFIED" in t for t in tests))
        self.assertTrue(any("UNKNOWN" in t for t in tests))


class TestSpecVersion(unittest.TestCase):
    def setUp(self):
        self.spec = load("spec_version.json")

    def test_hashes_present(self):
        for key in ["strategy_spec_hash", "parameter_spec_hash",
                    "evidence_binding_hash", "ea_build_contract_hash"]:
            self.assertTrue(self.spec[key], f"missing {key}")

    def test_evidence_model_hash_matches_frozen(self):
        self.assertTrue(self.spec["evidence_model_hash"].startswith("124F"))

    def test_semantic_versioning(self):
        self.assertIn("MAJOR.MINOR.PATCH",
                      self.spec["compatibility"]["semantic_versioning"])


class TestDeterministicHash(unittest.TestCase):
    def test_regeneration_produces_same_hash(self):
        """Rerun generator and verify spec hash unchanged."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools",
                                          "generate_strategy_spec.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr[-200:])
        self.assertIn("deterministic check = PASS", result.stdout)


class TestSpecSafety(unittest.TestCase):
    def test_no_mt5_in_strategy_spec(self):
        """Strategy spec must not contain MT5 execution directives."""
        spec_str = json.dumps(load("strategy_spec.json"))
        self.assertNotIn("order_send", spec_str)
        self.assertNotIn("OrderSend", spec_str)
        self.assertNotIn("import MetaTrader5", spec_str)

    def test_unknown_cannot_become_execution(self):
        invariants = load("invariant_spec.json")["invariants"]
        self.assertTrue(any("UNKNOWN" in inv["rule"] and "execution" in inv["rule"]
                            for inv in invariants))

    def test_frozen_hash_preserved(self):
        frozen = os.path.join(ROOT, "data", "evidence_model",
                              "V1.68-EVIDENCE-MODEL-v1.0.json")
        h = hashlib.sha256(open(frozen, "rb").read()).hexdigest().upper()
        self.assertTrue(h.startswith("124F08984284E880F268C37E"))


if __name__ == "__main__":
    unittest.main()
