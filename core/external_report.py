"""EXTERNAL_EVIDENCE_REPORT builder (Phase 3)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core.assumptions import default_registry
from core.environment import observed_test_environment
from core.evidence import default_evidence_registry
from core.external_evidence import (
    MYFXBOOK_LIMITATION,
    EvidenceLinkStore,
    ExternalEvidenceStore,
    QUALITY_UNKNOWN,
    SUPERSEDED,
    evidence_quality,
)
from core.model_candidates import ModelCandidateStore
from core.myfxbook import compare_environments

SCHEMA = "SNIPER_EXTERNAL_EVIDENCE_REPORT_V1"


def build_external_evidence_report(evidence_id: Optional[str] = None) -> dict:
    store = ExternalEvidenceStore()
    links = EvidenceLinkStore()
    candidates = ModelCandidateStore(link_store=links)
    reg = default_evidence_registry()

    all_ev = store.all()
    selected = [e for e in all_ev
                if evidence_id is None or e.evidence_id == evidence_id]
    superseded = [e for e in all_ev if e.status == SUPERSEDED]

    env_comparisons = []
    for e in selected:
        env_comparisons.append({
            "evidence_id": e.evidence_id,
            **compare_environments(e),
        })

    unknowns: List[str] = []
    for e in selected:
        for attr in ("published_at", "period_start", "period_end",
                     "account_type", "timeframe"):
            if not getattr(e, attr):
                unknowns.append(f"{e.evidence_id}.{attr} = UNKNOWN")
        if e.quality == QUALITY_UNKNOWN:
            unknowns.append(f"{e.evidence_id}.quality = UNKNOWN")

    conflicts = links.conflicts()
    areg = default_registry()
    linked_assumption_ids = []
    for l in links.all():
        if l.target_type == "ASSUMPTION":
            linked_assumption_ids.append(l.target_id)

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": MYFXBOOK_LIMITATION,
        # Source
        "source": [{
            "evidence_id": e.evidence_id, "source_type": e.source_type,
            "source_url": e.source_url, "normalized_url": e.normalized_url,
            "source_name": e.source_name,
            "retrieved_at": e.retrieved_at,                  # Retrieval Time
            "published_at": e.published_at or "UNKNOWN",
            "period": {"start": e.period_start or "UNKNOWN",
                       "end": e.period_end or "UNKNOWN"},     # Period
            "status": e.status, "quality": e.quality,
        } for e in selected],
        # Environment
        "environment": env_comparisons,
        "environment_observed_reference":
            observed_test_environment().to_dict(),
        # Metrics
        "metrics": [{
            "evidence_id": e.evidence_id,
            "metrics": [m.to_dict() for m in e.extracted_metrics],
            "extraction_status": e.extraction_status,
            "metric_kind": "OBSERVED_EXTERNAL_METRIC",
        } for e in selected],
        # Snapshots
        "snapshots": [{
            "evidence_id": e.evidence_id,
            "snapshots": [s.to_dict() for s in store.snapshots_for(e.evidence_id)],
        } for e in selected],
        "superseded_records": [e.evidence_id for e in superseded],
        # Linked evidence / assumptions / observations
        "linked_evidence": [l.to_dict() for l in links.all()],
        "linked_assumptions": areg.describe(list(dict.fromkeys(linked_assumption_ids))),
        "linked_observations": [l.to_dict() for l in links.all()
                                if l.target_type == "OBSERVATION"],
        # Candidate rules
        "candidate_rules": [c.to_dict() for c in candidates.all()],
        # Conflicts
        "conflicts": [c.to_dict() for c in conflicts],
        # Unknowns
        "unknowns": unknowns,
        # Limitations
        "limitations": [
            MYFXBOOK_LIMITATION,
            "Myfxbook data is INDIRECT evidence: usable for performance "
            "context / cross-check only, never as support for internal "
            "formula assumptions (enforced by the link gate).",
            "Multiple accounts keep separate environments - never aggregated "
            "into universal EA behavior.",
            "Pages that render metrics via JavaScript may not be parseable; "
            "the importer then reports IMPORT_FAILED with the reason instead "
            " of inventing data.",
        ],
        "registry_seeds": [r.evidence_id for r in reg.all()],
    }
