"""Web tests (Phase 1): registry endpoints must serialize from Core only."""
import unittest

from webhelpers import call_app


class RegistryEndpoints(unittest.TestCase):
    def test_evidence_endpoint(self):
        status, _, payload = call_app("GET", "/api/evidence")
        self.assertEqual(status, 200, payload)
        data = payload["data"]
        ids = {r["evidence_id"] for r in data["records"]}
        self.assertIn("E007", ids)
        e7 = [r for r in data["records"] if r["evidence_id"] == "E007"][0]
        self.assertEqual(e7["observed_value"], "90.0")
        self.assertEqual(e7["status"], "OBSERVED")
        self.assertEqual(e7["parameter"], "EmergencyDistanceFromCycleUSD")
        self.assertEqual(data["count"], len(data["records"]))

    def test_environment_endpoint(self):
        status, _, payload = call_app("GET", "/api/environment")
        self.assertEqual(status, 200, payload)
        data = payload["data"]
        env = data["observed"]
        self.assertEqual(env["platform"], "MT5")
        self.assertEqual(env["broker"], "XM Global")
        self.assertEqual(env["symbol"], "GOLDmicro")
        self.assertEqual(env["timeframe"], "M15")
        self.assertEqual(env["status"], "OBSERVED")
        # account number must never exist as a field
        self.assertNotIn("account_number", env)
        self.assertNotIn("account", env)
        self.assertIn("broker_profile", data)
        self.assertIn("not a universal rule", data["notes"])

    def test_parameters_endpoint(self):
        status, _, payload = call_app("GET", "/api/parameters")
        self.assertEqual(status, 200, payload)
        data = payload["data"]
        by_id = {p["parameter_id"]: p for p in data["parameters"]}
        self.assertEqual(by_id["PARAM_21"]["status"], "UNKNOWN")
        self.assertEqual(by_id["PARAM_21"]["code_name"], "AccumTargetUSD")
        kinds = {v["kind"]: v["value"]
                 for v in by_id["PARAM_18"]["value_records"]}
        self.assertEqual(kinds["OBSERVED VALUE"], 90.0)
        self.assertEqual(kinds["RECOMMENDED PRESET"], 50.0)

    def test_ex5_integrity_endpoint(self):
        status, _, payload = call_app("GET", "/api/ex5-integrity")
        self.assertEqual(status, 200, payload)
        rec = payload["data"]["record"]
        # workspace has no .ex5: honest status, no fabricated hash
        self.assertEqual(rec["status"], "SOURCE_FILE_NOT_PRESENT")
        self.assertIsNone(rec["sha256"])
        self.assertEqual(rec["historical_status"], "RECORDED_EXTERNAL_BASELINE")
        self.assertIn(rec["historical_sha256"],
                      ("31E5176E794C29BE265EBF1B449B1047F2125C57A1CD227B257F89A54BF9CE37",))

    def test_registry_endpoints_get_only(self):
        self.assertEqual(call_app("POST", "/api/evidence", {})[0], 405)
        self.assertEqual(call_app("POST", "/api/environment", {})[0], 405)
        self.assertEqual(call_app("POST", "/api/parameters", {})[0], 405)
        self.assertEqual(call_app("POST", "/api/ex5-integrity", {})[0], 405)

    def test_assumptions_endpoint_has_phase1_fields(self):
        status, _, payload = call_app("GET", "/api/assumptions")
        self.assertEqual(status, 200, payload)
        items = payload["data"]["assumptions"]
        by_id = {a["assumption_id"]: a for a in items}
        self.assertIn("TICK_VALUE_ASSUMPTION_001", by_id)
        self.assertIn("CYCLE_START_RULE_ASSUMPTION_001", by_id)
        tick = by_id["TICK_VALUE_ASSUMPTION_001"]
        self.assertEqual(tick["status"], "UNKNOWN")
        self.assertEqual(tick["category"], "Symbol specification")
        cyc = by_id["CYCLE_START_RULE_ASSUMPTION_001"]
        self.assertEqual(cyc["status"], "MODEL_ASSUMPTION")
        self.assertIn("core/cycle.py", cyc["affected_modules"])


if __name__ == "__main__":
    unittest.main()
