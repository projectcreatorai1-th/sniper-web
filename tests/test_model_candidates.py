"""Tests: ModelCandidate lifecycle + external report (Phase 3)."""
import json
import os
import shutil
import tempfile
import unittest

from core.external_evidence import (
    EvidenceLinkStore,
    ExternalEvidenceStore,
    REL_CONTRADICTS,
    REL_SUPPORTS,
    TARGET_ASSUMPTION,
)
from core.external_report import build_external_evidence_report
from core.model_candidates import (
    ACCEPTED,
    CANDIDATE,
    ModelCandidateStore,
    REJECTED,
    RULE_TYPES,
    SUPERSEDED,
)
from core.model_rules import ModelVersionStore, SimulationModelRules
from tests import std_ctx


class CandidateTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cand_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.links = EvidenceLinkStore(self.tmp)
        self.store = ModelCandidateStore(os.path.join(self.tmp, "c.json"),
                                         link_store=self.links)
        self.model_store = ModelVersionStore(os.path.join(self.tmp, "mv.json"))


class TestCandidateLifecycle(CandidateTestBase):
    def test_create(self):
        c = self.store.create("GRID_SPACING", "spacing ~5.0 in journal",
                              source_evidence_ids=["EX-1"])
        self.assertTrue(c.candidate_id.startswith("MC-"))
        self.assertEqual(c.status, CANDIDATE)
        self.assertFalse(c.reviewed_by)

    def test_create_validates(self):
        with self.assertRaises(ValueError):
            self.store.create("NOT_A_RULE", "x")
        with self.assertRaises(ValueError):
            self.store.create("OTHER", "   ")

    def test_accept_requires_reviewer(self):
        c = self.store.create("OTHER", "x")
        with self.assertRaises(ValueError):
            self.store.accept(c.candidate_id, "")
        self.assertEqual(self.store.get(c.candidate_id).status, CANDIDATE)

    def test_accept_applies_model_version_with_confirmation(self):
        c = self.store.create("LOT_FORMULA", "arithmetic fits observations",
                              source_evidence_ids=["EX-1"])
        rules = SimulationModelRules()
        accepted = self.store.accept(
            c.candidate_id, "lead-reviewer", "confirmed with journal data",
            rules_patch=rules.to_dict(), model_store=self.model_store)
        self.assertEqual(accepted.status, ACCEPTED)
        self.assertEqual(accepted.reviewed_by, "lead-reviewer")
        self.assertTrue(accepted.applied_model_version.startswith("SM-"))
        # model version history grew and records provenance
        entry = self.model_store.all_versions()[-1]
        self.assertEqual(entry.confirmed_by, "lead-reviewer")
        self.assertEqual(entry.based_on_evidence, ["EX-1"])
        self.assertEqual(entry.previous_version, "SM-001")

    def test_reject(self):
        c = self.store.create("OTHER", "x")
        r = self.store.reject(c.candidate_id, "reviewer", "weak evidence")
        self.assertEqual(r.status, REJECTED)
        with self.assertRaises(ValueError):   # already rejected
            self.store.accept(c.candidate_id, "reviewer2")

    def test_supersede(self):
        c = self.store.create("OTHER", "x")
        s = self.store.supersede(c.candidate_id, "rev", "better candidate MC-002")
        self.assertEqual(s.status, SUPERSEDED)

    def test_accepted_candidate_not_acceptable_again(self):
        c = self.store.create("OTHER", "x")
        self.store.accept(c.candidate_id, "r1")
        with self.assertRaises(ValueError):
            self.store.accept(c.candidate_id, "r2")


class TestCandidateConflicts(CandidateTestBase):
    def _make_conflict(self, evidence_ids):
        a, b = evidence_ids
        l1 = self.links.add(a, TARGET_ASSUMPTION, "GRID_DISTANCE_DOC_001",
                            REL_SUPPORTS)
        self.links.confirm(l1.link_id, "u1")
        l2 = self.links.add(b, TARGET_ASSUMPTION, "GRID_DISTANCE_DOC_001",
                            REL_CONTRADICTS)
        self.links.confirm(l2.link_id, "u2")

    def test_conflicting_evidence_blocks_accept(self):
        self._make_conflict(("EX-A", "EX-B"))
        c = self.store.create("GRID_SPACING", "based on conflicting ev",
                              source_evidence_ids=["EX-A", "EX-B"])
        with self.assertRaises(ValueError) as ctx:
            self.store.accept(c.candidate_id, "reviewer")
        self.assertIn("unresolved", str(ctx.exception))
        # resolve by removing one link -> accept works
        links = self.links.all()
        self.links.remove([l for l in links
                           if l.relation == REL_CONTRADICTS][0].link_id)
        ok = self.store.accept(c.candidate_id, "reviewer")
        self.assertEqual(ok.status, ACCEPTED)

    def test_conflicts_surfaced(self):
        self._make_conflict(("EX-A", "EX-B"))
        c = self.store.create("GRID_SPACING", "x", source_evidence_ids=["EX-A"])
        self.assertEqual(len(self.store.candidate_conflicts(c.candidate_id)), 1)


class TestExternalReport(unittest.TestCase):
    def test_report_sections_and_disclaimer(self):
        rep = build_external_evidence_report()
        for key in ("source", "environment", "metrics", "snapshots",
                    "linked_evidence", "linked_assumptions",
                    "linked_observations", "candidate_rules", "conflicts",
                    "unknowns", "limitations"):
            self.assertIn(key, rep)
        self.assertEqual(
            rep["disclaimer"],
            "External performance data does not prove internal EA formulas.")

    def test_report_filter_by_evidence(self):
        rep = build_external_evidence_report("EX-NOT-EXIST")
        self.assertEqual(rep["source"], [])

    def test_report_lists_limitations(self):
        rep = build_external_evidence_report()
        self.assertGreaterEqual(len(rep["limitations"]), 3)
        joined = " ".join(rep["limitations"])
        self.assertIn("INDIRECT", joined)
        self.assertIn("never aggregated", joined)


if __name__ == "__main__":
    unittest.main()
