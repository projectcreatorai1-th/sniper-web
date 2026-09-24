"""Model candidates (Phase 3): the human-gated rule-change flow.

    External Evidence / Observation -> Candidate Rule -> Human Review
        -> Confirm (reviewed_by) -> New Model Version

ACCEPT requires an explicit reviewer; accepting calls ModelVersionStore.
apply_new_version (which itself demands confirmed_by). Nothing auto-accepts,
nothing auto-learns. Conflicting evidence is surfaced, never auto-resolved.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

from core.external_evidence import (
    Conflict,
    EvidenceLinkStore,
    SRC_MYFXBOOK,
)
from core.external_evidence import SUPERSEDED

SCHEMA = "SNIPER_MODEL_CANDIDATE_V1"

CANDIDATE = "CANDIDATE"
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
CANDIDATE_STATUSES = (CANDIDATE, ACCEPTED, REJECTED, SUPERSEDED)

RULE_TYPES = (
    "LOT_FORMULA", "GRID_SPACING", "GRID_DIRECTION", "BASKET_SCOPE",
    "PARTIAL_CLOSE", "EMERGENCY", "CYCLE_RULE", "OTHER",
)

STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "model_candidates.json")


@dataclass
class ModelCandidate:
    candidate_id: str
    rule_type: str
    description: str
    source_evidence_ids: List[str] = field(default_factory=list)
    supporting_observations: List[str] = field(default_factory=list)
    contradicting_observations: List[str] = field(default_factory=list)
    status: str = CANDIDATE
    created_at: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
    review_note: str = ""
    applied_model_version: str = ""      # set when ACCEPTED created a version
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ModelCandidate":
        c = cls(candidate_id=d.get("candidate_id", "MC-?"),
                rule_type=d.get("rule_type", "OTHER"),
                description=d.get("description", ""))
        for k, v in d.items():
            if k in ("schema", "candidate_id"):
                continue
            if hasattr(c, k) and v is not None:
                setattr(c, k, v)
        return c


def _load(path: str) -> List[dict]:
    import json
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save(path: str, items: List[dict]) -> None:
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


class ModelCandidateStore:
    def __init__(self, path: Optional[str] = None,
                 link_store: Optional[EvidenceLinkStore] = None):
        self.path = path or STORE_PATH
        self.links = link_store or EvidenceLinkStore()

    def all(self) -> List[ModelCandidate]:
        return [ModelCandidate.from_dict(d) for d in _load(self.path)]

    def get(self, candidate_id: str) -> ModelCandidate:
        for c in self.all():
            if c.candidate_id == candidate_id:
                return c
        raise KeyError(candidate_id)

    def create(self, rule_type: str, description: str,
               source_evidence_ids: Optional[List[str]] = None,
               supporting_observations: Optional[List[str]] = None,
               notes: str = "") -> ModelCandidate:
        if rule_type not in RULE_TYPES:
            raise ValueError(f"rule_type must be one of {RULE_TYPES}")
        if not description or not description.strip():
            raise ValueError("description required")
        items = _load(self.path)
        cand = ModelCandidate(
            candidate_id=f"MC-{len(items) + 1:03d}",
            rule_type=rule_type, description=description.strip(),
            source_evidence_ids=list(source_evidence_ids or []),
            supporting_observations=list(supporting_observations or []),
            created_at=datetime.now().isoformat(timespec="seconds"),
            notes=notes)
        items.append(cand.to_dict())
        _save(self.path, items)
        return cand

    def _update(self, candidate_id: str, **patch) -> ModelCandidate:
        items = _load(self.path)
        for i in items:
            if i.get("candidate_id") == candidate_id:
                i.update(patch)
                _save(self.path, items)
                return ModelCandidate.from_dict(i)
        raise KeyError(candidate_id)

    def reject(self, candidate_id: str, reviewed_by: str,
               note: str = "") -> ModelCandidate:
        if not reviewed_by or not reviewed_by.strip():
            raise ValueError("rejection requires a human reviewer name")
        cand = self.get(candidate_id)
        if cand.status != CANDIDATE:
            raise ValueError(f"only CANDIDATE can be rejected (now: {cand.status})")
        return self._update(candidate_id, status=REJECTED,
                            reviewed_by=reviewed_by,
                            reviewed_at=datetime.now().isoformat(timespec="seconds"),
                            review_note=note)

    def supersede(self, candidate_id: str, reviewed_by: str,
                  note: str = "") -> ModelCandidate:
        if not reviewed_by or not reviewed_by.strip():
            raise ValueError("supersede requires a human reviewer name")
        return self._update(candidate_id, status=SUPERSEDED,
                            reviewed_by=reviewed_by,
                            reviewed_at=datetime.now().isoformat(timespec="seconds"),
                            review_note=note)

    def accept(self, candidate_id: str, reviewed_by: str, note: str = "",
               rules_patch: Optional[dict] = None,
               model_store=None) -> ModelCandidate:
        """ACCEPT - requires human confirmation; optionally applies a new
        model version through the Phase 2 gate (apply_new_version also
        demands confirmed_by). Myfxbook-only candidates cannot be accepted
        as formula proof."""
        if not reviewed_by or not reviewed_by.strip():
            raise ValueError("acceptance requires a human reviewer name")
        cand = self.get(candidate_id)
        if cand.status != CANDIDATE:
            raise ValueError(f"only CANDIDATE can be accepted (now: {cand.status})")

        conflicts = self.candidate_conflicts(candidate_id)
        if conflicts:
            raise ValueError(
                f"candidate has {len(conflicts)} unresolved evidence "
                "conflict(s) - resolve links first (no auto-resolution)")

        applied_version = ""
        if model_store is not None and rules_patch is not None:
            from core.model_rules import SimulationModelRules
            rules = SimulationModelRules.from_dict(rules_patch)
            new_rules = model_store.apply_new_version(
                rules, source="candidate-accepted",
                changes=[f"candidate {candidate_id}: {cand.description[:120]}"],
                notes=note,
                based_on_evidence=cand.source_evidence_ids,
                confirmed_by=reviewed_by)
            applied_version = new_rules.model_version
        return self._update(candidate_id, status=ACCEPTED,
                             reviewed_by=reviewed_by,
                             reviewed_at=datetime.now().isoformat(timespec="seconds"),
                             review_note=note,
                             applied_model_version=applied_version)

    # -- conflicts surfaced on the candidate (never auto-resolved) -------------
    def candidate_conflicts(self, candidate_id: str) -> List[Conflict]:
        cand = self.get(candidate_id)
        out = []
        for conflict in self.links.conflicts():
            if conflict.target_type == "ASSUMPTION" and any(
                    aid in conflict.supports + conflict.contradicts
                    for aid in cand.source_evidence_ids):
                out.append(conflict)
            elif conflict.target_type == "OBSERVATION" and any(
                    oid in conflict.supports + conflict.contradicts
                    for oid in cand.supporting_observations):
                out.append(conflict)
        return out
