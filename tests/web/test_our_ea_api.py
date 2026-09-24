"""P2/P3 runtime-service + API + freshness tests.

Covers: every /api/our_ea/* endpoint (read-only), operator command
interface (missing operator refused, mode transitions, DEMO blocked,
LIVE refused), provenance/freshness contract on every response,
session_id/correlation_id availability, boundary (runtime service has no
Analyzer imports; frozen hash unchanged; analyzer logic untouched),
malformed/missing-runtime handling, UI wiring (page JS must fetch live
API, not the static export).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from web.backend import our_ea_api
from web.backend.app import application
from core.our_ea.runtime_service import (RuntimeService, get_runtime_service,
                                         RUNTIME_VERSION)


def call(method, path, body=b""):
    env = {"REQUEST_METHOD": method, "PATH_INFO": path,
           "CONTENT_LENGTH": str(len(body)), "wsgi.input":
           __import__("io").BytesIO(body)}
    status_headers = {}
    def start_response(status, headers):
        status_headers["status"] = int(status.split()[0])
        status_headers["headers"] = dict(headers)
    chunks = application(env, start_response)
    return (status_headers["status"], status_headers["headers"],
            b"".join(chunks))


class TestRuntimeService(unittest.TestCase):
    def setUp(self):
        self.svc = RuntimeService()          # fresh instance per test

    def test_provenance_on_every_snapshot(self):
        for snap in (self.svc.status(), self.svc.state(),
                     self.svc.risk_status(), self.svc.reconciliation(),
                     self.svc.events(), self.svc.health()):
            p = snap.provenance
            self.assertEqual(p.runtime_version, RUNTIME_VERSION)
            self.assertGreater(p.state_version, 0)
            self.assertRegex(p.manifest_hash, r"^[0-9A-F]{64}$")
            self.assertTrue(p.trace_id)
            self.assertTrue(p.timestamp_utc.endswith("Z")
                            or "+" in p.timestamp_utc)
            self.assertTrue(p.session_id.startswith("RT-"))

    def test_mode_commands(self):
        r = self.svc.command_start_observation("OP")
        self.assertEqual(r["mode"], "OBSERVATION")
        r = self.svc.command_promote_shadow("OP")
        self.assertEqual(r["mode"], "SHADOW")

    def test_operator_required(self):
        for fn in (self.svc.command_start_observation,
                   self.svc.command_kill, self.svc.command_live):
            with self.assertRaises(ValueError):
                fn("   ")

    def test_demo_blocked_in_p3(self):
        r = self.svc.command_promote_demo("OP")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "ENVIRONMENT-BLOCKED")

    def test_live_refused_with_audit(self):
        r = self.svc.command_live("OP")
        self.assertEqual(r["error"], "LIVE_LOCKED")
        self.assertTrue(self.svc.event_log.by_type(
            "LIVE_EXECUTION_REQUESTED"))

    def test_kill_blocks_and_audits(self):
        r = self.svc.command_kill("OP")
        self.assertTrue(r["ok"])
        self.assertTrue(self.svc.kill_board.blocks_new_orders())
        self.assertTrue(self.svc.event_log.by_type("SAFE_STOP"))

    def test_events_carry_session_and_correlation(self):
        self.svc.command_start_observation("OP")
        view = self.svc.events()
        for e in view.latest:
            self.assertTrue(e.get("session_id"))
            self.assertTrue(e.get("correlation_id"))

    def test_mt5_truthfully_not_connected(self):
        self.assertEqual(self.svc.status().mt5_connection, "NOT_CONNECTED")
        rec = self.svc.reconciliation()
        self.assertEqual(rec.status, "NOT_CONNECTED")
        self.assertIn("fake", rec.note.lower())   # policy statement


class TestOurEaApi(unittest.TestCase):
    def test_all_read_endpoints_ok_with_provenance(self):
        for path in ("/api/our_ea/health", "/api/our_ea/status",
                     "/api/our_ea/runtime", "/api/our_ea/state",
                     "/api/our_ea/risk", "/api/our_ea/events",
                     "/api/our_ea/reconciliation", "/api/our_ea/manifest"):
            status, _h, body = call("GET", path)
            self.assertEqual(status, 200, path)
            d = json.loads(body)
            self.assertTrue(d["ok"], path)
            data = d["data"]
            prov = (data.get("provenance") or
                    (data.get("status") or {}).get("provenance"))
            if path != "/api/our_ea/manifest":
                self.assertTrue(prov and prov["manifest_hash"], path)

    def test_commands_require_operator(self):
        status, _h, body = call("POST", "/api/our_ea/command/kill", b"{}")
        self.assertEqual(status, 400)
        self.assertIn("OPERATOR_REQUIRED", body.decode())

    def test_live_command_refused_over_api(self):
        body = json.dumps({"operator": "AUDITOR"}).encode()
        status, _h, out = call("POST", "/api/our_ea/command/live", body)
        d = json.loads(out)
        self.assertTrue(d["ok"])               # audit-probe reports refusal
        self.assertEqual(d["data"]["error"], "LIVE_LOCKED")

    def test_demo_command_blocked_over_api(self):
        body = json.dumps({"operator": "OP"}).encode()
        status, _h, out = call("POST", "/api/our_ea/command/promote_demo", body)
        d = json.loads(out)
        self.assertEqual(d["data"]["error"], "ENVIRONMENT-BLOCKED")

    def test_unknown_route_404(self):
        status, _h, _b = call("GET", "/api/our_ea/nope")
        self.assertEqual(status, 404)
        status, _h, _b = call("DELETE", "/api/our_ea/status")
        self.assertEqual(status, 404)          # read-only, no mutations

    def test_malformed_json_400(self):
        status, _h, _b = call("POST", "/api/our_ea/command/kill", b"{bad")
        self.assertEqual(status, 400)

    def test_no_trading_endpoints_exist(self):
        for path in ("/api/our_ea/order", "/api/our_ea/trade",
                     "/api/our_ea/open", "/api/our_ea/close"):
            self.assertFalse(our_ea_api.handles("POST", path), path)


class TestFreshnessContract(unittest.TestCase):
    def test_manifest_hash_matches_file(self):
        svc = get_runtime_service()
        real = hashlib.sha256(open(os.path.join(
            ROOT, "release_manifest.json"), "rb").read()).hexdigest().upper()
        self.assertEqual(svc.status().provenance.manifest_hash, real)

    def test_frozen_hash_exposed_and_correct(self):
        svc = get_runtime_service()
        real = hashlib.sha256(open(os.path.join(
            ROOT, "data", "evidence_model",
            "V1.68-EVIDENCE-MODEL-v1.0.json"), "rb").read()
        ).hexdigest().upper()
        self.assertEqual(svc.status().evidence_model_hash, real)

    def test_stale_export_not_used_by_ui(self):
        js = open(os.path.join(ROOT, "web", "frontend", "our_ea",
                               "our_ea_page.js"), encoding="utf-8").read()
        self.assertIn("/api/our_ea/", js)
        self.assertNotIn("release_status.json", js,
                         "UI must not read the stale static export")

    def test_ui_detects_missing_provenance(self):
        js = open(os.path.join(ROOT, "web", "frontend", "our_ea",
                               "our_ea_page.js"), encoding="utf-8").read()
        self.assertIn("STALE", js)
        self.assertIn("OFFLINE", js)


class TestRuntimeBoundary(unittest.TestCase):
    def test_runtime_service_imports_no_analyzer(self):
        src = open(os.path.join(ROOT, "core", "our_ea",
                                "runtime_service.py"), encoding="utf-8").read()
        for bad in ("core.calculations", "core.forensics", "core.evidence",
                    "core.cycle", "core.basket", "MetaTrader5"):
            self.assertNotIn(f"from {bad}", src)
            self.assertNotIn(f"import {bad}", src)

    def test_frozen_and_analyzer_unchanged(self):
        r = subprocess.run(
            ["git", "diff", "--name-only", "6bdb67c", "HEAD", "--",
             "core/calculations.py", "core/evidence.py", "core/cycle.py",
             "core/basket.py", "core/forensics", "desktop",
             "data/evidence.json", "data/model_candidates.json",
             "data/evidence_model"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "")


class TestHistoricalLedgerCompat(unittest.TestCase):
    def test_event_without_session_fields_still_valid(self):
        from core.our_ea.events import Event
        e = Event(event_id="E-old", timestamp="t", event_type="ENTRY",
                  model_version="V")          # no session/correlation
        e.validate()
        self.assertEqual(e.session_id, "")
        self.assertEqual(e.correlation_id, "")


if __name__ == "__main__":
    unittest.main()
