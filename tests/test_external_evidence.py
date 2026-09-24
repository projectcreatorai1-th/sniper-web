"""Tests: External Evidence v2 model, snapshots, links, conflicts (Phase 3)."""
import os
import shutil
import tempfile
import unittest

from core.assumptions import default_registry
from core.external_evidence import (
    EXTRACTION_IMPORTED,
    LINK_RELATIONS,
    QUALITY_CONTEXTUAL,
    QUALITY_DIRECT,
    QUALITY_INDIRECT,
    QUALITY_UNKNOWN,
    REL_CONTRADICTS,
    REL_CONTEXT_FOR,
    REL_SUPPORTS,
    SRC_MANUAL,
    SRC_MYFXBOOK,
    SUPERSEDED,
    TARGET_ASSUMPTION,
    TARGET_OBSERVATION,
    EvidenceLinkStore,
    EvidenceSnapshot,
    ExternalEvidence,
    ExternalEvidenceStore,
    ExternalMetric,
    content_hash,
    evidence_quality,
    indirect_support_gate,
    metrics_hash,
)
from tests import TempDirTestMixin


class TestExternalEvidenceModel(unittest.TestCase):
    def test_full_field_set(self):
        ev = ExternalEvidence(
            evidence_id="EX-1", source_type=SRC_MYFXBOOK,
            source_url="https://original.example/x",
            normalized_url="https://normalized.example/x",
            retrieved_at="2026-09-24T10:00:00",
            account_type="Hedge", broker="XM Global", platform="MT5",
            symbol="GOLDmicro", timeframe="M15",
            period_start="2024-01-02", period_end="2024-06-30",
            extracted_metrics=[ExternalMetric(key="profit_factor", value=1.66)],
            extraction_status=EXTRACTION_IMPORTED)
        d = ev.to_dict()
        for key in ("evidence_id", "source_type", "source_url", "source_name",
                    "retrieved_at", "published_at", "account_type", "broker",
                    "platform", "symbol", "timeframe", "period_start",
                    "period_end", "raw_reference", "extracted_metrics",
                    "extraction_status", "confidence", "notes",
                    "linked_assumptions"):
            self.assertIn(key, d)
        self.assertNotIn("account_number", d)      # sensitive: never stored
        ev2 = ExternalEvidence.from_dict(ev.to_dict())
        self.assertEqual(ev2.metric_dict(), {"profit_factor": 1.66})

    def test_metrics_are_observed_external_kind(self):
        m = ExternalMetric(key="profit", value=123.4)
        self.assertEqual(m.kind, "OBSERVED_EXTERNAL_METRIC")

    def test_unknown_stays_unknown_not_invented(self):
        ev = ExternalEvidence()
        self.assertEqual(ev.published_at, "")
        self.assertEqual(ev.period_start, "")
        self.assertEqual(ev.extraction_status, "INTERFACE READY")

    def test_quality_classification(self):
        self.assertEqual(evidence_quality("MT5_JOURNAL"), QUALITY_DIRECT)
        self.assertEqual(evidence_quality(SRC_MYFXBOOK), QUALITY_INDIRECT)
        self.assertEqual(evidence_quality("VIDEO"), QUALITY_CONTEXTUAL)
        self.assertEqual(evidence_quality("WEIRD"), QUALITY_UNKNOWN)


class TestHashesAndSnapshots(TempDirTestMixin, unittest.TestCase):
    def test_hashes(self):
        raw = b"abc"
        self.assertEqual(content_hash(raw),
                         "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD")
        self.assertEqual(metrics_hash({"a": 1, "b": 2}),
                         metrics_hash({"b": 2, "a": 1}))
        self.assertNotEqual(metrics_hash({"a": 1}), metrics_hash({"a": 2}))

    def test_snapshot_persist_and_history_preserved(self):
        store = ExternalEvidenceStore(self.tmpdir)
        ev = ExternalEvidence(evidence_id="EX-9", source_type=SRC_MYFXBOOK)
        store.save(ev)
        s1 = EvidenceSnapshot("S-1", "EX-9", "t1", "H1", "M1")
        store.add_snapshot(s1)
        s2 = EvidenceSnapshot("S-2", "EX-9", "t2", "H2", "M2")
        store.add_snapshot(s2)
        snaps = store.snapshots_for("EX-9")
        self.assertEqual([s.snapshot_id for s in snaps], ["S-1", "S-2"])
        # append-only: re-adding never overwrites history
        store.add_snapshot(EvidenceSnapshot("S-3", "EX-9", "t3", "H3", "M3"))
        self.assertEqual(len(store.snapshots_for("EX-9")), 3)

    def test_supersede_keeps_old_record(self):
        store = ExternalEvidenceStore(self.tmpdir)
        store.save(ExternalEvidence(evidence_id="EX-A"))
        store.mark_superseded("EX-A", "EX-B")
        got = store.get("EX-A")
        self.assertEqual(got.status, SUPERSEDED)
        self.assertEqual(got.superseded_by, "EX-B")


class TestLinksAndConfirmation(unittest.TestCase):
    def setUp(self):
        import tempfile as _t, shutil as _s, os as _o
        self.tmpdir = _t.mkdtemp(prefix="links_")
        self.addCleanup(_s.rmtree, self.tmpdir, ignore_errors=True)
        self.links = EvidenceLinkStore(self.tmpdir)

    def test_link_unlink(self):
        l = self.links.add("EX-1", TARGET_ASSUMPTION,
                           "GRID_DISTANCE_DOC_001", REL_CONTEXT_FOR)
        self.assertFalse(l.confirmed())
        self.assertTrue(self.links.remove(l.link_id))
        self.assertFalse(self.links.remove(l.link_id))

    def test_confirm_requires_human(self):
        l = self.links.add("EX-1", TARGET_ASSUMPTION,
                           "GRID_DISTANCE_DOC_001", REL_CONTEXT_FOR)
        with self.assertRaises(ValueError):
            self.links.confirm(l.link_id, "")
        done = self.links.confirm(l.link_id, "tester", "note")
        self.assertTrue(done.confirmed())
        self.assertEqual(done.confirmed_by, "tester")
        self.assertTrue(done.confirmed_at)

    def test_relations_and_duplicate_rejected(self):
        for rel in (REL_SUPPORTS, REL_CONTRADICTS, REL_CONTEXT_FOR):
            self.links.add("EX-R", TARGET_OBSERVATION, f"OBS-{rel}", rel)
        with self.assertRaises(ValueError):
            self.links.add("EX-R", TARGET_ASSUMPTION, "X", "proves")
        l = self.links.add("EX-R", TARGET_ASSUMPTION, "GRID_TRIGGER_ASSUMPTION_001",
                           REL_SUPPORTS)
        with self.assertRaises(KeyError):
            self.links.add("EX-R", TARGET_ASSUMPTION,
                           "GRID_TRIGGER_ASSUMPTION_001", REL_SUPPORTS)

    def test_conflict_detection(self):
        a = self.links.add("EX-1", TARGET_ASSUMPTION,
                           "GRID_DISTANCE_DOC_001", REL_SUPPORTS)
        self.links.confirm(a.link_id, "u1")
        self.assertEqual(self.links.conflicts(), [])   # support alone = no conflict
        b = self.links.add("EX-2", TARGET_ASSUMPTION,
                           "GRID_DISTANCE_DOC_001", REL_CONTRADICTS)
        self.assertEqual(self.links.conflicts(), [])   # unconfirmed = not counted
        self.links.confirm(b.link_id, "u2")
        conflicts = self.links.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].supports, ["EX-1"])
        self.assertEqual(conflicts[0].contradicts, ["EX-2"])

    def test_unconfirmed_links_do_not_conflict(self):
        self.links.add("EX-1", TARGET_ASSUMPTION, "A", REL_SUPPORTS)
        self.links.add("EX-2", TARGET_ASSUMPTION, "A", REL_CONTRADICTS)
        self.assertEqual(self.links.conflicts(), [])


class TestIndirectGate(unittest.TestCase):
    def test_myfxbook_cannot_support_formula_assumptions(self):
        ev = ExternalEvidence(source_type=SRC_MYFXBOOK)
        reason = indirect_support_gate(ev, REL_SUPPORTS, TARGET_ASSUMPTION,
                                       "LOT_FORMULA_ASSUMPTION_001")
        self.assertIsNotNone(reason)
        self.assertIn("does not prove internal EA formulas", reason)

    def test_context_for_allowed_for_formulas(self):
        ev = ExternalEvidence(source_type=SRC_MYFXBOOK)
        self.assertIsNone(indirect_support_gate(
            ev, REL_CONTEXT_FOR, TARGET_ASSUMPTION, "LOT_FORMULA_ASSUMPTION_001"))

    def test_indirect_may_contradict(self):
        ev = ExternalEvidence(source_type=SRC_MYFXBOOK)
        self.assertIsNone(indirect_support_gate(
            ev, REL_CONTRADICTS, TARGET_ASSUMPTION, "LOT_FORMULA_ASSUMPTION_001"))

    def test_direct_evidence_may_support_non_formula(self):
        ev = ExternalEvidence(source_type="MT5_JOURNAL")
        self.assertIsNone(indirect_support_gate(
            ev, REL_SUPPORTS, TARGET_ASSUMPTION, "GRID_DISTANCE_DOC_001"))

    def test_all_formula_assumptions_exist_in_registry(self):
        from core.external_evidence import FORMULA_ASSUMPTION_IDS
        reg = default_registry()
        for aid in FORMULA_ASSUMPTION_IDS:
            self.assertIsNotNone(reg.try_get(aid), aid)


if __name__ == "__main__":
    unittest.main()
