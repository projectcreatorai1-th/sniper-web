"""Tests: Myfxbook importer + environment comparison (Phase 3)."""
import os
import unittest
import urllib.error

from core.external_evidence import (
    EXTRACTION_PARTIAL,
    SRC_MYFXBOOK,
    SUPERSEDED,
    ExternalEvidence,
    ExternalEvidenceStore,
    QUALITY_INDIRECT,
)
from core.myfxbook import (
    MyfxbookImporter,
    compare_environments,
    default_fetch,
    normalize_myfxbook_url,
    parse_myfxbook_html,
)
from core.environment import observed_test_environment
from tests import TempDirTestMixin

GOOD_HTML = """
<html><body>
Broker: XM Global Platform: MT5 Symbol: GOLDmicro Timeframe: M15
Balance 5,000.00 Equity 5,100.00 Profit 1,250.50
Profit Factor 1.66 Drawdown 12.5% Trades 410 Lots 88.2
Long trades 220 Short trades 190
Period 2024-01-02 to 2024-06-30
</body></html>
"""


def make_store(tmpdir):
    return ExternalEvidenceStore(tmpdir)


class TestUrlNormalization(unittest.TestCase):
    def test_variants_normalize(self):
        base = "https://www.myfxbook.com/members/user/acct/123"
        self.assertEqual(normalize_myfxbook_url(base), base)
        self.assertEqual(normalize_myfxbook_url(
            "http://myfxbook.com/members/user/acct/123"), base)
        self.assertEqual(normalize_myfxbook_url(
            "myfxbook.com/members/user/acct/123#tab"), base)

    def test_non_myfxbook_rejected(self):
        from core.external_evidence import ExternalEvidenceError
        with self.assertRaises(ExternalEvidenceError):
            normalize_myfxbook_url("https://example.com/x")
        with self.assertRaises(ExternalEvidenceError):
            normalize_myfxbook_url("")


class TestParsing(unittest.TestCase):
    def test_numeric_metrics_parsed(self):
        metrics, env, p1, p2, warns = parse_myfxbook_html(GOOD_HTML)
        self.assertAlmostEqual(metrics["profit_factor"], 1.66)
        self.assertAlmostEqual(metrics["drawdown"], 12.5)
        self.assertEqual(metrics["trades"], 410)
        self.assertEqual(metrics["balance"], 5000.0)
        self.assertEqual(metrics["long_trades"], 220)
        self.assertEqual(env["broker"], "XM Global")
        self.assertEqual(env["platform"], "MT5")
        self.assertEqual(p1, "2024-01-02")
        self.assertEqual(p2, "2024-06-30")

    def test_missing_values_absent_not_zero(self):
        metrics, _, _, _, _ = parse_myfxbook_html("<html><body>nothing</body></html>")
        self.assertEqual(metrics, {})          # no invented values

    def test_unknown_period(self):
        _, _, p1, p2, warns = parse_myfxbook_html(
            "<html><body>Profit Factor 1.5</body></html>")
        self.assertIsNone(p1)
        self.assertIsNone(p2)
        self.assertTrue(any("period" in w for w in warns))


class TestImporter(TempDirTestMixin, unittest.TestCase):
    def test_valid_import(self):
        imp = MyfxbookImporter(make_store(self.tmpdir),
                               fetch=lambda u: GOOD_HTML.encode())
        r = imp.import_url("https://www.myfxbook.com/members/u/a/1")
        self.assertEqual(r["status"], "IMPORTED")
        ev = r["evidence"]
        self.assertEqual(ev["source_type"], SRC_MYFXBOOK)
        self.assertEqual(ev["quality"], QUALITY_INDIRECT)
        self.assertEqual(ev["extraction_status"], EXTRACTION_PARTIAL)
        self.assertTrue(ev["source_url"].startswith("https://www.myfxbook.com"))
        self.assertIn("OBSERVED_EXTERNAL_METRIC", ev["notes"])
        self.assertTrue(r["snapshot"]["content_hash"])

    def test_invalid_url(self):
        imp = MyfxbookImporter(make_store(self.tmpdir), fetch=lambda u: b"")
        r = imp.import_url("https://example.com/nope")
        self.assertEqual(r["status"], "IMPORT_FAILED")
        self.assertIn("not a myfxbook URL", r["reason"])

    def test_inaccessible_source(self):
        def boom(u):
            raise urllib.error.URLError("dns failure")
        imp = MyfxbookImporter(make_store(self.tmpdir), fetch=boom)
        r = imp.import_url("https://www.myfxbook.com/members/u/a/2")
        self.assertEqual(r["status"], "IMPORT_FAILED")
        self.assertIn("network error", r["reason"])

    def test_http_error(self):
        def http_err(u):
            raise urllib.error.HTTPError(u, 404, "Not Found", {}, None)
        imp = MyfxbookImporter(make_store(self.tmpdir), fetch=http_err)
        r = imp.import_url("https://www.myfxbook.com/members/u/a/3")
        self.assertEqual(r["status"], "IMPORT_FAILED")
        self.assertIn("HTTP 404", r["reason"])

    def test_malformed_no_metrics(self):
        imp = MyfxbookImporter(make_store(self.tmpdir),
                               fetch=lambda u: b"<html>JS app shell</html>")
        r = imp.import_url("https://www.myfxbook.com/members/u/a/4")
        self.assertEqual(r["status"], "IMPORT_FAILED")
        self.assertIn("no recognizable metrics", r["reason"])
        self.assertIn("no data invented", r["reason"])

    def test_duplicate_import_same_content(self):
        store = make_store(self.tmpdir)
        imp = MyfxbookImporter(store, fetch=lambda u: GOOD_HTML.encode())
        r1 = imp.import_url("https://www.myfxbook.com/members/u/a/5")
        r2 = imp.import_url("https://www.myfxbook.com/members/u/a/5")
        self.assertTrue(r2["duplicate"])
        self.assertTrue(r2["unchanged"])
        self.assertEqual(r1["evidence"]["evidence_id"],
                         r2["evidence"]["evidence_id"])
        self.assertEqual(len(store.snapshots_for(r1["evidence"]["evidence_id"])), 2)

    def test_changed_content_supersedes(self):
        store = make_store(self.tmpdir)
        html_v1 = GOOD_HTML
        html_v2 = GOOD_HTML.replace("1.66", "1.77")
        imp = MyfxbookImporter(store, fetch=lambda u: html_v1.encode())
        r1 = imp.import_url("https://www.myfxbook.com/members/u/a/6")
        imp2 = MyfxbookImporter(store, fetch=lambda u: html_v2.encode())
        r2 = imp2.import_url("https://www.myfxbook.com/members/u/a/6")
        old = store.get(r1["evidence"]["evidence_id"])
        self.assertEqual(old.status, SUPERSEDED)
        self.assertEqual(old.superseded_by, r2["evidence"]["evidence_id"])
        # old record still retrievable with its snapshots (history preserved)
        self.assertTrue(store.snapshots_for(old.evidence_id))

    def test_no_fake_fallback_ever(self):
        # even total garbage returns a reasoned failure, never fake evidence
        imp = MyfxbookImporter(make_store(self.tmpdir), fetch=lambda u: b"\x00\x01")
        r = imp.import_url("https://www.myfxbook.com/members/u/a/7")
        self.assertIn(r["status"], ("IMPORT_FAILED",))
        self.assertTrue(r.get("reason"))


class TestEnvironmentComparison(unittest.TestCase):
    def _ev(self, **kw):
        return ExternalEvidence(source_type=SRC_MYFXBOOK, **kw)

    def _status(self, ev):
        return compare_environments(ev)["overall"]

    def test_exact_match(self):
        ev = self._ev(platform="MT5", broker="XM Global", symbol="GOLDmicro",
                      account_type="Hedge", timeframe="M15")
        self.assertEqual(self._status(ev), "MATCH")

    def test_partial_match(self):
        ev = self._ev(platform="MT5", broker="XM Global", symbol="",
                      account_type="", timeframe="")
        self.assertEqual(self._status(ev), "PARTIAL_MATCH")

    def test_mismatch_different_broker(self):
        ev = self._ev(platform="MT5", broker="IC Markets", symbol="XAUUSD",
                      account_type="Hedge", timeframe="M15")
        self.assertEqual(self._status(ev), "MISMATCH")

    def test_unknown_all_fields_missing(self):
        self.assertEqual(self._status(self._ev()), "UNKNOWN")

    def test_rows_never_guess(self):
        result = compare_environments(self._ev(broker=""))
        row = [r for r in result["rows"] if r["field"] == "broker"][0]
        self.assertEqual(row["status"], "UNKNOWN")
        self.assertEqual(row["external"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
