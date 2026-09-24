"""Web tests (Phase 3): evidence + candidate endpoints (in-process WSGI)."""
import unittest

HTML = ("<html><body>Broker: XM Global Platform: MT5 Symbol: GOLDmicro "
        "Timeframe: M15 Profit Factor 1.66 Drawdown 12.5% Trades 410 "
        "Period 2024-01-02 to 2024-06-30</body></html>")

import core.myfxbook as mf
_real_fetch = mf.default_fetch


class EvidenceEndpoints(unittest.TestCase):
    eid = None
    link_id = None

    @classmethod
    def setUpClass(cls):
        # inject a deterministic fetch for the live-server test process
        mf.default_fetch = lambda url, timeout=20: HTML.encode()
        from core.external_evidence import ExternalEvidenceStore
        import tempfile, shutil
        cls.tmp = tempfile.mkdtemp(prefix="ev_api_")
        cls.store = ExternalEvidenceStore(cls.tmp)
        import web.backend.evidence_api as ea
        from core.external_evidence import EvidenceLinkStore
        from core.model_candidates import ModelCandidateStore
        import os
        ea._ev_store = cls.store
        ea._links = EvidenceLinkStore(cls.tmp)
        ea._cands = ModelCandidateStore(
            os.path.join(cls.tmp, "cand.json"), link_store=ea._links)

    @classmethod
    def tearDownClass(cls):
        mf.default_fetch = _real_fetch
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_import_myfxbook(self):
        from webhelpers import call_app
        s, _, p = call_app("POST", "/api/evidence/myfxbook/import",
                           {"url": "https://www.myfxbook.com/members/t/e/1"})
        self.assertEqual(s, 200, p)
        self.eid = p["data"]["evidence"]["evidence_id"]
        EvidenceEndpoints.eid = self.eid
        self.assertEqual(p["data"]["evidence"]["quality"], "INDIRECT")
        self.assertTrue(p["data"]["snapshot"]["content_hash"])

    def test_02_list_external(self):
        if EvidenceEndpoints.eid is None:
            self.skipTest("import failed")
        from webhelpers import call_app
        s, _, p = call_app("GET", "/api/evidence/external")
        self.assertEqual(s, 200)
        ids = [e["evidence_id"] for e in p["data"]["evidence"]]
        self.assertIn(EvidenceEndpoints.eid, ids)

    def test_03_detail_with_env_comparison(self):
        from webhelpers import call_app
        s, _, p = call_app("GET", f"/api/evidence/{EvidenceEndpoints.eid}")
        self.assertEqual(s, 200)
        comp = p["data"]["environment_comparison"]
        self.assertIn(comp["overall"], ("MATCH", "PARTIAL_MATCH", "MISMATCH", "UNKNOWN"))
        rows = {r["field"]: r["status"] for r in comp["rows"]}
        self.assertEqual(rows.get("broker"), "MATCH")

    def test_04_snapshots(self):
        from webhelpers import call_app
        s, _, p = call_app("GET",
                           f"/api/evidence/{EvidenceEndpoints.eid}/snapshots")
        self.assertEqual(s, 200)
        self.assertGreaterEqual(p["data"]["count"], 1)

    def test_05_link_gate_and_confirm(self):
        from webhelpers import call_app
        eid = EvidenceEndpoints.eid
        # INDIRECT may NOT support a formula assumption
        s, _, p = call_app("POST", f"/api/evidence/{eid}/link", {
            "target_type": "ASSUMPTION", "target_id": "LOT_FORMULA_ASSUMPTION_001",
            "relation": "supports"})
        self.assertEqual(s, 400)
        self.assertEqual(p["error"]["code"], "LINK_REJECTED_BY_QUALITY_GATE")
        # context_for is allowed
        s, _, p = call_app("POST", f"/api/evidence/{eid}/link", {
            "target_type": "ASSUMPTION", "target_id": "LOT_FORMULA_ASSUMPTION_001",
            "relation": "context_for"})
        self.assertEqual(s, 200, p)
        link_id = p["data"]["link"]["link_id"]
        self.assertFalse(p["data"]["link"]["confirmed_by"])
        # confirm requires reviewer
        s, _, p = call_app("POST", f"/api/evidence/{eid}/confirm", {
            "link_id": link_id, "confirmed_by": ""})
        self.assertEqual(s, 400)
        s, _, p = call_app("POST", f"/api/evidence/{eid}/confirm", {
            "link_id": link_id, "confirmed_by": "tester", "note": "ok"})
        self.assertEqual(s, 200)
        self.assertEqual(p["data"]["link"]["confirmed_by"], "tester")
        EvidenceEndpoints.link_id = link_id

    def test_06_unlink(self):
        if EvidenceEndpoints.link_id is None:
            self.skipTest("no link created")
        from webhelpers import call_app
        s, _, p = call_app("POST", "/api/evidence/unlink",
                           {"link_id": EvidenceEndpoints.link_id})
        self.assertEqual(s, 200)

    def test_07_unknown_evidence_404(self):
        from webhelpers import call_app
        s, _, p = call_app("GET", "/api/evidence/EX-NOPE")
        self.assertEqual(s, 400)
        self.assertEqual(p["error"]["code"], "NOT_FOUND")

    def test_08_import_failures_honest(self):
        from webhelpers import call_app
        s, _, p = call_app("POST", "/api/evidence/myfxbook/import",
                           {"url": "https://example.com/x"})
        self.assertEqual(s, 400)
        self.assertEqual(p["error"]["code"], "IMPORT_FAILED")
        self.assertIn("not a myfxbook URL", p["error"]["message"])
        s, _, p = call_app("POST", "/api/evidence/myfxbook/import", {})
        self.assertEqual(s, 400)

    def test_09_candidates_flow(self):
        from webhelpers import call_app
        eid = EvidenceEndpoints.eid
        s, _, p = call_app("POST", "/api/model-candidates", {
            "rule_type": "GRID_SPACING", "description": "test candidate",
            "source_evidence_ids": [eid]})
        self.assertEqual(s, 200, p)
        cid = p["data"]["candidate"]["candidate_id"]
        # accept without reviewer -> rejected
        s, _, p = call_app("POST", f"/api/model-candidates/{cid}/confirm",
                           {"reviewed_by": ""})
        self.assertEqual(s, 400)
        # unknown action
        s, _, p = call_app("POST", f"/api/model-candidates/{cid}/teleport", {})
        self.assertEqual(s, 405)
        # reject with reviewer
        s, _, p = call_app("POST", f"/api/model-candidates/{cid}/reject",
                           {"reviewed_by": "tester", "note": "weak"})
        self.assertEqual(s, 200)
        self.assertEqual(p["data"]["candidate"]["status"], "REJECTED")

    def test_10_conflicts_and_report(self):
        from webhelpers import call_app
        s, _, p = call_app("GET", "/api/evidence/conflicts")
        self.assertEqual(s, 200)
        s, _, p = call_app("GET", "/api/evidence/report")
        self.assertEqual(s, 200)
        self.assertIn("does not prove internal EA formulas",
                      p["data"]["disclaimer"])
        for key in ("source", "metrics", "snapshots", "candidate_rules",
                    "conflicts", "unknowns", "limitations"):
            self.assertIn(key, p["data"])


if __name__ == "__main__":
    unittest.main()
