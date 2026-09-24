"""Web tests (Phase 2): observation-session endpoints end-to-end."""
import unittest

from webhelpers import call_app, multipart_body

VALID_CSV = "\n".join([
    "Time,Event,Side,Level,Lot,Price,TotalLots,BasketPL,Commission,Swap",
    "2024.01.02 10:00:00,open,BUY,1,0.10,2050.0,0.10,,",
    "2024.01.02 10:30:00,add,BUY,2,0.11,2045.0,0.21,,",
    "2024.01.02 10:50:00,add,BUY,3,0.12,2040.0,0.33,,",
    "2024.01.02 11:30:00,basket_close,BUY,,0.33,2048.0,,1.70,-0.20,-0.05",
]) + "\n"


class ObservationFlow(unittest.TestCase):
    def setUp(self):
        s, _, p = call_app("POST", "/api/observation-sessions",
                           {"symbol": "XAUUSD", "timeframe": "M15",
                            "source_type": "MT5_CSV"})
        self.assertEqual(s, 200, p)
        self.sid = p["data"]["session"]["session_id"]
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        from core.observation import ObservationSessionStore
        ObservationSessionStore().delete(self.sid)

    def test_create_validates_fields(self):
        s, _, p = call_app("POST", "/api/observation-sessions", {"hack": 1})
        self.assertEqual(s, 400)
        s, _, p = call_app("POST", "/api/observation-sessions",
                           {"source_type": "NOPE"})
        self.assertEqual(s, 400)
        s, _, p = call_app("POST", "/api/observation-sessions",
                           {"parameters": {"BaseLot": "abc"}})
        self.assertEqual(s, 400)

    def test_full_flow_import_events_comparison_timeline_report(self):
        body, ctype = multipart_body("obs.csv", VALID_CSV)
        s, _, p = call_app("POST",
                           f"/api/observation-sessions/{self.sid}/import",
                           body, content_type=ctype)
        self.assertEqual(s, 200, p)
        self.assertEqual(p["data"]["import_result"]["rows_imported"], 4)
        self.assertEqual(p["data"]["event_count"], 4)

        s, _, p = call_app("GET", f"/api/observation-sessions/{self.sid}")
        self.assertEqual(s, 200)
        self.assertEqual(p["data"]["event_count"], 4)
        self.assertNotIn("events", p["data"]["session"])  # summary only

        s, _, p = call_app("GET",
                           f"/api/observation-sessions/{self.sid}/events")
        self.assertEqual(s, 200)
        self.assertEqual(len(p["data"]["events"]), 4)
        close = p["data"]["events"][-1]
        self.assertEqual(close["commission"], -0.2)      # cost data survives
        self.assertIsNone(p["data"]["events"][0]["commission"])  # UNKNOWN stays

        s, _, p = call_app("GET",
                           f"/api/observation-sessions/{self.sid}/comparison")
        self.assertEqual(s, 200)
        self.assertEqual(p["data"]["schema"], "SNIPER_BEHAVIOR_COMPARISON_V1")
        self.assertGreater(len(p["data"]["checks"]), 10)
        ids = [c["check_id"] for c in p["data"]["checks"]]
        self.assertIn("GRID-BUY-SECOND", ids)
        self.assertIn("BASKET-TARGET", ids)
        self.assertIn("EMG-VALUES", ids)

        s, _, p = call_app("GET",
                           f"/api/observation-sessions/{self.sid}/timeline")
        self.assertEqual(s, 200)
        self.assertEqual(p["data"]["cycle_count"], 1)

        s, _, p = call_app("GET",
                           f"/api/observation-sessions/{self.sid}/report")
        self.assertEqual(s, 200)
        self.assertEqual(p["data"]["schema"],
                         "SNIPER_BEHAVIOR_VERIFICATION_REPORT_V1")

    def test_unknown_session_404_like(self):
        s, _, p = call_app("GET", "/api/observation-sessions/OBS-NOPE/events")
        self.assertEqual(s, 400)
        self.assertIn("not found", p["error"]["message"])

    def test_import_rejects_bad_type_and_empty(self):
        body, ctype = multipart_body("evil.py", "print(1)")
        s, _, p = call_app("POST",
                           f"/api/observation-sessions/{self.sid}/import",
                           body, content_type=ctype)
        self.assertEqual(s, 400)
        self.assertEqual(p["error"]["code"], "UNSUPPORTED_FILE_TYPE")
        body, ctype = multipart_body("empty.csv", " \n")
        s, _, p = call_app("POST",
                           f"/api/observation-sessions/{self.sid}/import",
                           body, content_type=ctype)
        self.assertEqual(s, 400)

    def test_method_gating(self):
        self.assertEqual(
            call_app("POST", f"/api/observation-sessions/{self.sid}/events",
                     {})[0], 405)
        self.assertEqual(
            call_app("GET", "/api/observation-sessions")[0], 405)

    def test_test_plans_endpoint(self):
        s, _, p = call_app("GET", "/api/test-plans")
        self.assertEqual(s, 200)
        self.assertEqual(len(p["data"]["test_plans"]), 6)


if __name__ == "__main__":
    unittest.main()
