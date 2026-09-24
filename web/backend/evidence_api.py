"""Phase 3 evidence/candidate API handlers - real core functionality only."""
from __future__ import annotations

import json
from typing import Optional

from core.external_evidence import (
    LINK_RELATIONS,
    LINK_TARGET_TYPES,
    SUPERSEDED,
    ExternalEvidenceStore,
    ExternalEvidenceError,
    EvidenceLinkStore,
    indirect_support_gate,
)
from core.external_report import build_external_evidence_report
from core.model_candidates import ModelCandidateStore, RULE_TYPES
from core.myfxbook import MyfxbookImporter
from web.backend.parsers import RequestError

_ev_store: Optional[ExternalEvidenceStore] = None
_links: Optional[EvidenceLinkStore] = None
_cands: Optional[ModelCandidateStore] = None


def stores():
    global _ev_store, _links, _cands
    if _ev_store is None:
        _ev_store = ExternalEvidenceStore()
    if _links is None:
        _links = EvidenceLinkStore()
    if _cands is None:
        _cands = ModelCandidateStore(link_store=_links)
    return _ev_store, _links, _cands


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------
def list_external_evidence() -> dict:
    store, links, _ = stores()
    items = []
    for e in store.all():
        linked = [l.to_dict() for l in links.all()
                  if l.evidence_id == e.evidence_id]
        items.append({**e.to_dict(),
                      "snapshots": len(store.snapshots_for(e.evidence_id)),
                      "links": linked})
    return {"evidence": items, "count": len(items),
            "statuses": ["OBSERVED", "DOCUMENTED", "MODEL", "UNKNOWN", SUPERSEDED],
            "relations": list(LINK_RELATIONS),
            "quality": ["DIRECT", "INDIRECT", "CONTEXTUAL", "UNKNOWN"]}


def import_myfxbook(body: dict) -> dict:
    if not isinstance(body, dict) or not body.get("url"):
        raise RequestError("'url' is required")
    store, _, _ = stores()
    importer = MyfxbookImporter(store)
    result = importer.import_url(str(body["url"]),
                                 notes=str(body.get("notes", "")))
    if result["status"] != "IMPORTED":
        raise RequestError(
            f"Myfxbook import failed: {result.get('reason', 'unknown')}",
            code="IMPORT_FAILED",
            details=[result.get("reason", "")] if result.get("reason") else None)
    return {"result": {k: v for k, v in result.items() if k != "evidence"},
            "evidence": result["evidence"],
            "snapshot": result["snapshot"],
            "warnings": result["warnings"]}


def get_evidence_detail(evidence_id: str) -> dict:
    store, links, cands = stores()
    try:
        ev = store.get(evidence_id)
    except KeyError:
        raise RequestError(f"evidence not found: {evidence_id}", "NOT_FOUND")
    from core.myfxbook import compare_environments
    return {"evidence": ev.to_dict(),
            "snapshots": [s.to_dict() for s in store.snapshots_for(evidence_id)],
            "links": [l.to_dict() for l in links.all()
                      if l.evidence_id == evidence_id],
            "candidates": [c.to_dict() for c in cands.all()
                           if evidence_id in c.source_evidence_ids],
            "environment_comparison": compare_environments(ev)}


def get_snapshots(evidence_id: str) -> dict:
    store, _, _ = stores()
    try:
        store.get(evidence_id)
    except KeyError:
        raise RequestError(f"evidence not found: {evidence_id}", "NOT_FOUND")
    snaps = store.snapshots_for(evidence_id)
    return {"evidence_id": evidence_id, "count": len(snaps),
            "snapshots": [s.to_dict() for s in snaps]}


def link_evidence(evidence_id: str, body: dict) -> dict:
    store, links, _ = stores()
    try:
        ev = store.get(evidence_id)
    except KeyError:
        raise RequestError(f"evidence not found: {evidence_id}", "NOT_FOUND")
    target_type = body.get("target_type")
    target_id = (body.get("target_id") or "").strip()
    relation = body.get("relation")
    if target_type not in LINK_TARGET_TYPES:
        raise RequestError(f"target_type must be one of {LINK_TARGET_TYPES}")
    if not target_id:
        raise RequestError("'target_id' is required")
    if relation not in LINK_RELATIONS:
        raise RequestError(f"relation must be one of {LINK_RELATIONS}")
    if target_type == "ASSUMPTION":
        from core.assumptions import default_registry
        if default_registry().try_get(target_id) is None:
            raise RequestError(f"unknown assumption id: {target_id}")

    gate_reason = indirect_support_gate(ev, relation, target_type, target_id)
    if gate_reason:
        raise RequestError(gate_reason, code="LINK_REJECTED_BY_QUALITY_GATE")

    try:
        link = links.add(evidence_id, target_type, target_id, relation)
    except KeyError as exc:
        raise RequestError(str(exc))
    # keep the evidence record's convenience lists in sync
    if target_type == "ASSUMPTION" and target_id not in ev.linked_assumptions:
        ev.linked_assumptions.append(target_id)
        store.save(ev)
    return {"link": link.to_dict(),
            "note": "unconfirmed until a human confirms the relationship"}


def confirm_link(evidence_id: str, body: dict) -> dict:
    _, links, _ = stores()
    link_id = (body or {}).get("link_id", "")
    confirmed_by = (body or {}).get("confirmed_by", "")
    note = (body or {}).get("note", "")
    if not link_id:
        raise RequestError("'link_id' is required")
    target = None
    for l in links.all():
        if l.link_id == link_id and l.evidence_id == evidence_id:
            target = l
    if target is None:
        raise RequestError(f"link not found on evidence {evidence_id}", "NOT_FOUND")
    try:
        links.confirm(link_id, confirmed_by, note)
    except ValueError as exc:
        raise RequestError(str(exc))
    return {"link": next(l.to_dict() for l in links.all()
                         if l.link_id == link_id)}


def unlink(body: dict) -> dict:
    _, links, _ = stores()
    link_id = (body or {}).get("link_id", "")
    if not link_id:
        raise RequestError("'link_id' is required")
    if not links.remove(link_id):
        raise RequestError(f"link not found: {link_id}", "NOT_FOUND")
    return {"removed": link_id}


def conflicts() -> dict:
    _, links, _ = stores()
    items = [c.to_dict() for c in links.conflicts()]
    return {"conflicts": items, "count": len(items),
            "note": "Conflicts are reported, never auto-resolved."}


def external_report(evidence_id: Optional[str] = None) -> dict:
    return build_external_evidence_report(evidence_id)


# ---------------------------------------------------------------------------
# model candidates
# ---------------------------------------------------------------------------
def _cand_store():
    _, _, cands = stores()
    return cands


def list_candidates() -> dict:
    cands = _cand_store()
    _, links, _ = stores()
    return {"candidates": [c.to_dict() for c in cands.all()],
            "rule_types": list(RULE_TYPES),
            "statuses": ["CANDIDATE", "ACCEPTED", "REJECTED", "SUPERSEDED"]}


def create_candidate(body: dict) -> dict:
    cands = _cand_store()
    try:
        cand = cands.create(
            rule_type=body.get("rule_type", "OTHER"),
            description=body.get("description", ""),
            source_evidence_ids=body.get("source_evidence_ids") or [],
            supporting_observations=body.get("supporting_observations") or [],
            notes=body.get("notes", ""))
    except ValueError as exc:
        raise RequestError(str(exc))
    return {"candidate": cand.to_dict()}


def _review_action(candidate_id: str, body: dict, action: str) -> dict:
    cands = _cand_store()
    reviewed_by = (body or {}).get("reviewed_by", "")
    note = (body or {}).get("note", "")
    try:
        if action == "confirm":
            rules_patch = body.get("rules_patch")
            from core.model_rules import ModelVersionStore
            cand = cands.accept(candidate_id, reviewed_by, note,
                                rules_patch=rules_patch,
                                model_store=ModelVersionStore())
        elif action == "reject":
            cand = cands.reject(candidate_id, reviewed_by, note)
        elif action == "supersede":
            cand = cands.supersede(candidate_id, reviewed_by, note)
        else:
            raise RequestError(f"unknown action: {action}")
    except ValueError as exc:
        raise RequestError(str(exc))
    except KeyError:
        raise RequestError(f"candidate not found: {candidate_id}", "NOT_FOUND")
    return {"candidate": cand.to_dict()}
