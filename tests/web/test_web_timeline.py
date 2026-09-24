"""Web tests (Phase 4): timeline simulation + observation picker + exports."""
import unittest

from webhelpers import call_app

import core.myfxbook as mf
_real_fetch = mf.default_fetch


class TimelineEndpoints(unittest.TestCase):
    def test_scenarios_list(self):
        s, _, p = call_app("GET", "/api/timeline/scenarios")
        self.assertEqual(s, 200)
        self.assertIn("NORMAL_DOWN", p["data"]["scenarios"])
        self.assertIn("SYNTHETIC", p["data"]["note"])

    def test_simulate_basic(self):
        s, _, p = call_app("POST", "/api/timeline/simulate",
                           {"scenario": "NORMAL_DOWN", "bars": 30, "step": 1.0})
        self.assertEqual(s, 200, p)
        sim = p["data"]["simulation"]
        self.assertTrue(sim["synthetic"])
        self.assertIn("SYNTHETIC", sim["notes"])
        self.assertTrue(sim["events"])
        self.assertTrue(all(e["label"] == "MODEL ASSUMPTION" for e in sim["events"]))
        trace = p["data"]["trace"]
        self.assertEqual(trace["model_version"], "SM-001")
        self.assertTrue(trace["assumption_ids"])
        mvs = p["data"]["model_vs_simulation"]
        self.assertTrue(all(r["status"] == "MODEL_ONLY" for r in mvs["rows"]))

    def test_simulate_costs_unknown(self):
        s, _, p = call_app("POST", "/api/timeline/simulate",
                           {"scenario": "NORMAL_UP", "bars": 20})
        for e in p["data"]["simulation"]["events"]:
            self.assertIsNone(e["commission"])
            self.assertIsNone(e["swap"])
            self.assertIsNone(e["net_pnl"])

    def test_simulate_unknown_scenario(self):
        s, _, p = call_app("POST", "/api/timeline/simulate",
                           {"scenario": "MOON_WALK"})
        self.assertEqual(s, 400)

    def test_worst_case_pins_unchanged(self):
        """The timeline is a view — worst-case SSOT pins must hold exactly."""
        s, _, p = call_app("POST", "/api/timeline/worst-case",
                           {"capital": 500, "move": 50, "scenario": "BOTH_SIDES"})
        self.assertEqual(s, 200, p)
        wc = p["data"]["timeline"]["summary"]
        self.assertEqual(wc["grid_levels"], 11)
        self.assertAlmostEqual(wc["total_lots"], 1.91)
        self.assertAlmostEqual(wc["floating_pl"], -3200.0)
        self.assertAlmostEqual(wc["drawdown_pct"], 640.0)
        events = p["data"]["timeline"]["events"]
        grids = [e for e in events if e["event"] in ("ENTRY", "GRID")]
        self.assertEqual(len(grids), 11)

    def test_export_csv_json_html(self):
        s, _, body = call_app("POST", "/api/timeline/export",
                              {"scenario": "NORMAL_DOWN", "bars": 20,
                               "format": "csv"})
        self.assertEqual(s, 200)
        self.assertIn(b"timestamp", body[:500])
        s, _, body = call_app("POST", "/api/timeline/export",
                              {"scenario": "NORMAL_DOWN", "bars": 20,
                               "format": "html"})
        self.assertEqual(s, 200)
        self.assertIn(b"SYNTHETIC", body[:500])
        s, _, body = call_app("POST", "/api/timeline/export",
                              {"scenario": "NORMAL_DOWN", "bars": 20,
                               "format": "json"})
        self.assertEqual(s, 200)
        self.assertIn("simulation", body)


class ObservationPicker(unittest.TestCase):
    def test_picker_lists_sessions(self):
        s, _, p = call_app("POST", "/api/observation-picker", {})
        self.assertEqual(s, 200)
        self.assertIn("sessions", p["data"])

    def test_validate_rejects_unknown_session(self):
        s, _, p = call_app("POST", "/api/observation-picker/validate",
                           {"observation_id": "OBS-FAKE-999"})
        self.assertEqual(s, 400)
        self.assertEqual(p["error"]["code"], "REJECT")

    def test_validate_rejects_bad_event_index(self):
        # create a real session first
        s, _, p = call_app("POST", "/api/observation-sessions",
                           {"source_type": "MT5_CSV"})
        sid = p["data"]["session"]["session_id"]
        self.addCleanup(self._cleanup, sid)
        s, _, p = call_app("POST", "/api/observation-picker/validate",
                           {"observation_id": sid, "event_index": 99})
        self.assertEqual(s, 400)
        self.assertEqual(p["error"]["code"], "REJECT")
        s, _, p = call_app("POST", "/api/observation-picker/validate",
                           {"observation_id": sid})
        self.assertEqual(s, 200)
        self.assertTrue(p["data"]["valid"])

    @staticmethod
    def _cleanup(sid):
        from core.observation import ObservationSessionStore
        ObservationSessionStore().delete(sid)


class MethodGates(unittest.TestCase):
    def test_wrong_methods(self):
        self.assertEqual(call_app("GET", "/api/timeline/simulate")[0], 405)
        self.assertEqual(call_app("POST", "/api/timeline/scenarios", {})[0], 405)
        self.assertEqual(call_app("GET", "/api/observation-picker")[0], 405)


if __name__ == "__main__":
    unittest.main()
