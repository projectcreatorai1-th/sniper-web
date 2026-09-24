"""Tests: Evidence Registry + ExternalEvidence interface (Phase 1)."""
import os
import tempfile
import shutil
import unittest

from core.evidence import (
    DOCUMENTATION,
    DOCUMENTED,
    EVIDENCE_STATUSES,
    EvidenceRecord,
    EvidenceRegistry,
    ExternalEvidence,
    INTERFACE_READY,
    MYFXBOOK,
    OBSERVED,
    SOURCE_TYPES,
    UNKNOWN,
    VIDEO,
    default_evidence_registry,
)
from tests import TempDirTestMixin


class TestBaselineSeeds(unittest.TestCase):
    def setUp(self):
        self.reg = default_evidence_registry()

    def test_seed_records_exist(self):
        ids = {r.evidence_id for r in self.reg.all()}
        for eid in [f"E{n:03d}" for n in range(1, 11)]:
            self.assertIn(eid, ids)

    def test_every_seed_has_status(self):
        for r in self.reg.all():
            self.assertIn(r.status, EVIDENCE_STATUSES, r.evidence_id)

    def test_emergency_observed_90_is_observed(self):
        r = self.reg.get("E007")
        self.assertEqual(r.observed_value, "90.0")
        self.assertEqual(r.status, OBSERVED)
        self.assertEqual(r.source_type, VIDEO)
        self.assertIn("not proof of internal EA logic", r.notes)

    def test_preset_50_is_documented(self):
        r = self.reg.get("E008")
        self.assertEqual(r.observed_value, "50.0")
        self.assertEqual(r.status, DOCUMENTED)


class TestRegistryCrud(TempDirTestMixin, unittest.TestCase):
    def test_create_retrieve(self):
        reg = EvidenceRegistry(os.path.join(self.tmpdir, "ev.json"))
        rec = EvidenceRecord(evidence_id="X001", source_type=VIDEO,
                             source_name="test video", claim="c",
                             observed_value="1", status=OBSERVED,
                             confidence="MEDIUM")
        reg.add(rec)
        self.assertEqual(reg.get("X001").claim, "c")
        self.assertEqual(len(reg.all()), 11)  # 10 seeds + 1

    def test_invalid_status_rejected(self):
        reg = EvidenceRegistry(None)
        with self.assertRaises(ValueError):
            reg.add(EvidenceRecord(evidence_id="X002", source_type=VIDEO,
                                   source_name="s", status="WOW"))

    def test_invalid_source_type_rejected(self):
        reg = EvidenceRegistry(None)
        with self.assertRaises(ValueError):
            reg.add(EvidenceRecord(evidence_id="X003", source_type="telepathy",
                                   source_name="s", status=OBSERVED))

    def test_invalid_confidence_rejected(self):
        reg = EvidenceRegistry(None)
        with self.assertRaises(ValueError):
            reg.add(EvidenceRecord(evidence_id="X004", source_type=VIDEO,
                                   source_name="s", status=OBSERVED,
                                   confidence="CERTAIN"))

    def test_duplicate_id_rejected_without_overwrite(self):
        reg = EvidenceRegistry(None)
        reg.add(EvidenceRecord(evidence_id="X005", source_type=VIDEO,
                               source_name="s", status=OBSERVED))
        with self.assertRaises(KeyError):
            reg.add(EvidenceRecord(evidence_id="X005", source_type=VIDEO,
                                   source_name="s2", status=UNKNOWN))

    def test_persistence_roundtrip(self):
        path = os.path.join(self.tmpdir, "ev2.json")
        reg = EvidenceRegistry(path)
        reg.add(EvidenceRecord(evidence_id="X006", source_type=MYFXBOOK,
                               source_name="myfxbook", claim="ext",
                               status=OBSERVED, confidence="LOW"))
        reg2 = EvidenceRegistry(path)
        self.assertEqual(reg2.get("X006").source_type, MYFXBOOK)

    def test_find_filter_by_source_type(self):
        reg = EvidenceRegistry(None)
        videos = reg.find(source_type=VIDEO)
        self.assertTrue(videos)
        self.assertTrue(all(r.source_type == VIDEO for r in videos))


class TestSourceTypes(unittest.TestCase):
    def test_canonical_list(self):
        self.assertEqual(SOURCE_TYPES, (
            DOCUMENTATION, "IMAGE", VIDEO, "MT5_BACKTEST", "MT5_JOURNAL",
            "MT5_CSV", "MANUAL_OBSERVATION", MYFXBOOK, "OTHER"))


class TestExternalEvidenceInterface(unittest.TestCase):
    def test_model_exists_and_marks_interface_ready(self):
        ext = ExternalEvidence(source_url="", source_name="myfxbook-account")
        d = ext.to_dict()
        self.assertEqual(d["import_status"], INTERFACE_READY)
        self.assertIn("source_url", d)
        self.assertIn("metrics", d)
        self.assertIn("retrieved_at", d)

    def test_roundtrip(self):
        ext = ExternalEvidence(source_name="s", trade_count=42,
                               metrics={"profit_factor": 1.9})
        d = ext.to_dict()
        ext2 = ExternalEvidence.from_dict(d)
        self.assertEqual(ext2.trade_count, 42)
        self.assertEqual(ext2.metrics["profit_factor"], 1.9)

    def test_no_fake_data_by_default(self):
        ext = ExternalEvidence()
        self.assertIsNone(ext.trade_count)
        self.assertEqual(ext.events, [])
        self.assertEqual(ext.metrics, {})


if __name__ == "__main__":
    unittest.main()
