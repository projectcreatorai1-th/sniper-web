"""API behavior tests (in-process WSGI): config/assumptions endpoints,
response envelope, malformed inputs, validation refusals, report formats.
"""
import json
import os
import unittest

from core.config import EAConfig
from core.worst_case import DEFAULT_MOVE_PRESETS

from webhelpers import call_app, std_body


class GetEndpoints(unittest.TestCase):
    def test_health(self):
        status, _, payload = call_app("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["status"], "ok")
        self.assertEqual(payload["data"]["ea_version"], "1.68")
        self.assertIn("Simulation Model", payload["data"]["disclaimer"])

    def test_config_endpoint(self):
        status, _, payload = call_app("GET", "/api/config")
        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertEqual(data["parameter_count"], 27)
        self.assertEqual(len(data["parameter_meta"]), 27)
        self.assertEqual(len(data["presets"]), 3)
        self.assertEqual(len(data["profiles"]), 3)
        self.assertEqual(data["move_presets"], list(DEFAULT_MOVE_PRESETS))
        self.assertEqual(data["defaults"]["GridStepUSD"], 5.0)
        self.assertEqual(data["defaults"]["schema"], "SNIPER_V1_68_CONFIG")
        self.assertEqual(data["model_rules"]["model_version"], "SM-001")
        th = data["risk_thresholds_default"]
        self.assertEqual(th["high_dd_percent"], 30.0)
        self.assertEqual(th["reference_adverse_move_usd"], 50.0)

    def test_assumptions_endpoint(self):
        status, _, payload = call_app("GET", "/api/assumptions")
        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertGreaterEqual(len(data["assumptions"]), 20)
        statuses = {a["status"] for a in data["assumptions"]}
        self.assertIn("VERIFIED_FROM_DOCUMENTATION", statuses)
        self.assertIn("MODEL_ASSUMPTION", statuses)
        self.assertIn("UNKNOWN", statuses)
        ids = [a["assumption_id"] for a in data["assumptions"]]
        self.assertIn("EA_BEHAVIOR_NOT_VERIFIED_001", ids)
        self.assertIn("MAX_GRID_DEPTH_UNKNOWN_001", ids)

    def test_unknown_api_404(self):
        status, _, payload = call_app("GET", "/api/nope")
        self.assertEqual(status, 404)
        self.assertFalse(payload["ok"])

    def test_method_not_allowed(self):
        self.assertEqual(call_app("POST", "/api/health")[0], 405)
        self.assertEqual(call_app("GET", "/api/grid/calculate")[0], 405)
        self.assertEqual(call_app("PUT", "/api/validate", std_body())[0], 405)

    def test_security_headers(self):
        status, headers, _ = call_app("GET", "/api/health")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")


class MalformedInput(unittest.TestCase):
    def _expect_400(self, path, body, raw=None, content_type="application/json"):
        status, _, payload = call_app("POST", path, raw if raw is not None else body,
                                      content_type)
        self.assertEqual(status, 400, payload)
        self.assertFalse(payload["ok"])
        self.assertIn("message", payload["error"])
        return payload

    def test_body_not_json(self):
        self._expect_400("/api/validate", None, raw=b"this is not json")

    def test_body_json_array(self):
        self._expect_400("/api/validate", None, raw=b"[1,2,3]")

    def test_empty_body(self):
        self._expect_400("/api/validate", None, raw=b"")

    def test_config_unknown_key(self):
        payload = self._expect_400("/api/validate", std_body(
            config=dict(EAConfig().to_dict(), TypoParam=1)))
        self.assertIn("TypoParam", payload["error"]["message"])

    def test_config_wrong_type(self):
        self._expect_400("/api/validate", std_body(
            config=dict(EAConfig().to_dict(), GridStepUSD="abc")))

    def test_symbol_profile_unknown_key(self):
        self._expect_400("/api/validate", std_body(symbol_profile={"nope": 1}))

    def test_account_unknown_key(self):
        self._expect_400("/api/validate", std_body(account={"hack": 1}))

    def test_model_rules_invalid(self):
        self._expect_400("/api/worst-case/simulate", std_body(
            capital=500.0, moves=[50.0],
            model_rules={"lot_formula": "NOSUCH"}))

    def test_grid_levels_out_of_range(self):
        self._expect_400("/api/grid/calculate", std_body(levels=0, side="BUY"))
        self._expect_400("/api/grid/calculate", std_body(levels=501, side="BUY"))

    def test_grid_bad_side(self):
        self._expect_400("/api/grid/calculate", std_body(levels=5, side="UP"))

    def test_grid_missing_levels(self):
        self._expect_400("/api/grid/calculate", std_body(side="BUY"))

    def test_worst_case_missing_capital(self):
        self._expect_400("/api/worst-case/simulate", std_body(moves=[50.0]))

    def test_worst_case_negative_move(self):
        self._expect_400("/api/worst-case/simulate",
                         std_body(capital=500.0, moves=[-5.0]))

    def test_worst_case_bad_scenario(self):
        self._expect_400("/api/worst-case/simulate",
                         std_body(capital=500.0, moves=[50.0], scenarios=["SIDEWAYS"]))

    def test_worst_case_empty_moves(self):
        self._expect_400("/api/worst-case/simulate",
                         std_body(capital=500.0, moves=[]))

    def test_thresholds_unknown_key(self):
        self._expect_400("/api/risk/calculate",
                         std_body(capital=500.0, thresholds={"oops": 1}))

    def test_basket_missing_levels(self):
        self._expect_400("/api/basket/simulate", std_body(side="BUY"))

    def test_basket_bad_partial_flag(self):
        self._expect_400("/api/basket/simulate",
                         std_body(side="BUY", levels=5, partial_already_done="yes"))

    def test_set_builder_missing_values(self):
        self._expect_400("/api/set-builder/generate", std_body(capital=500.0))

    def test_set_builder_missing_required_list(self):
        self._expect_400("/api/set-builder/generate", std_body(
            values={"base_lot": [0.1], "multiplier": [1.1], "capital": [500.0]}))

    def test_set_builder_unknown_value_key(self):
        self._expect_400("/api/set-builder/generate", std_body(values={
            "grid_step": [5.0], "base_lot": [0.1], "multiplier": [1.1],
            "capital": [500.0], "mystery": [1.0]}))

    def test_set_builder_too_many_combos(self):
        values = {
            "grid_step": [5.0 + i * 0.1 for i in range(25)],
            "base_lot": [0.1],
            "multiplier": [1.08 + i * 0.01 for i in range(25)],
            "capital": [500.0], "basket_target": [1.68], "max_grid": [11],
        }
        payload = self._expect_400("/api/set-builder/generate",
                                   std_body(values=values))
        self.assertEqual(payload["error"]["code"], "TOO_MANY_COMBINATIONS")

    def test_report_bad_format(self):
        self._expect_400("/api/report", std_body(format="pdf", capital=500.0))

    def test_report_bad_backtest_payload(self):
        self._expect_400("/api/report", std_body(
            format="json", capital=500.0, backtest_summary=[1, 2]))

    def test_json_body_too_large(self):
        big = {"pad": "x" * (2 * 1024 * 1024 + 100)}
        status, _, payload = call_app("POST", "/api/validate", big)
        self.assertEqual(status, 413)
        self.assertEqual(payload["error"]["code"], "PAYLOAD_TOO_LARGE")


class ResponseContract(unittest.TestCase):
    def test_calc_response_has_assumptions_and_disclaimer(self):
        status, _, payload = call_app("POST", "/api/grid/calculate",
                                      std_body(levels=5, side="BUY", capital=500.0))
        data = payload["data"]
        self.assertTrue(payload["ok"])
        self.assertEqual(data["disclaimer"],
                         "Simulation Model — not verified internal EA formula")
        self.assertIn("LOT_FORMULA_ASSUMPTION_001", data["assumptions"])
        detail = {d["assumption_id"]: d for d in data["assumption_details"]}
        self.assertEqual(detail["LOT_FORMULA_ASSUMPTION_001"]["status"],
                         "MODEL_ASSUMPTION")
        self.assertEqual(detail["GRID_TRIGGER_ASSUMPTION_001"]["status"],
                         "MODEL_ASSUMPTION")
        # validation warnings attached (INFO: emergency off is default)
        self.assertIsInstance(data["validation"], list)

    def test_report_csv_format(self):
        status, headers, payload = call_app(
            "POST", "/api/report", std_body(format="csv", capital=500.0))
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        text = payload.decode("utf-8-sig")
        self.assertIn("SECTION", text)
        self.assertIn("ea_config", text)

    def test_report_html_format(self):
        status, headers, payload = call_app(
            "POST", "/api/report", std_body(format="html", capital=500.0))
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        text = payload.decode("utf-8")
        self.assertIn("<html>", text)
        self.assertIn("SIMULATION MODEL", text)
        self.assertIn("Assumptions Used", text)

    def test_backtest_requires_multipart(self):
        status, _, payload = call_app("POST", "/api/backtest/analyze",
                                      std_body(), content_type="application/json")
        self.assertEqual(status, 400)
        self.assertIn("multipart", payload["error"]["message"])


class FrontendAssets(unittest.TestCase):
    """The frontend is served by this same backend - guard its integrity."""

    WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "web", "frontend")

    def test_index_references_assets(self):
        with open(os.path.join(self.WEB_DIR, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("/static/style.css", html)
        self.assertIn("/static/app.js", html)
        self.assertIn("Simulation Model", html)

    def test_app_js_syntax_valid(self):
        """node --check the frontend script (skipped when node is absent)."""
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        r = subprocess.run([node, "--check", os.path.join(self.WEB_DIR, "app.js")],
                           capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))

    def test_app_js_has_no_formula_duplication_markers(self):
        """Guard-rail: the frontend must not reimplement core formulas.
        It may only call the API and format results (field names from API
        responses are fine; exponentiation for lot/multiplier math is not)."""
        with open(os.path.join(self.WEB_DIR, "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("apiPost", js)                 # talks to the backend
        self.assertIn("Simulation Model", js)        # disclaimer present
        self.assertNotIn("Math.pow(", js)            # no lot formula re-implementation
        self.assertNotIn("Math.log(", js)
        self.assertNotIn("**", js)                   # no JS exponent operator


if __name__ == "__main__":
    unittest.main()
