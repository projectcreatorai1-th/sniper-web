"""Machine-readable Rule Registry (§9) + uncertainty records (§13).

Rules are loaded from the frozen contract (never mutated here). Each rule
gains implementation metadata (implementation_status, implementation_ref,
test_ref) that lives ONLY in OUR EA — the frozen model is untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.our_ea.contract import (ModelVersion, load_contract,
                                  rules_from_contract)

VERIFIED = "VERIFIED"
PARTIAL = "PARTIAL"
UNKNOWN = "UNKNOWN"
REJECTED = "REJECTED"
SUPERSEDED = "SUPERSEDED"
RULE_STATUSES = (VERIFIED, PARTIAL, UNKNOWN, REJECTED, SUPERSEDED)

# Canonical rule ids used across OUR EA code/tests/traceability.
RULE_LOT_FLOOR = "R-LOT-FLOOR"
RULE_BASE_LOT = "R-BASE-LOT"
RULE_GRID_SPACING = "R-GRID-SPACING"
RULE_GRID_DIRECTION = "R-GRID-DIRECTION"
RULE_BOTH_SIDES = "R-BOTH-SIDES"
RULE_CONTRACT_SIZE = "R-CONTRACT-SIZE"
RULE_PARTIAL_EXISTS = "R-PARTIAL-EXISTS"
RULE_NORMAL_RESUME = "R-NORMAL-RESUME"
RULE_GRID_TRIGGER = "R-GRID-TRIGGER"
RULE_BASKET_TRIGGER = "R-BASKET-TRIGGER"
RULE_PARTIAL_LEVEL = "R-PARTIAL-LEVEL"
RULE_PARTIAL_TRIGGER = "R-PARTIAL-TRIGGER"
RULE_PARTIAL_VOLUME = "R-PARTIAL-VOLUME"
RULE_EMERGENCY = "R-EMERGENCY"
RULE_RESTART_RECOVERY = "R-RESTART-RECOVERY"
RULE_ACCUM_1_68 = "R-ACCUM-1-68"

# frozen-model rule name -> canonical OUR EA rule id
_RULE_NAME_MAP = {
    "Lot Formula (floor ladder)": RULE_LOT_FLOOR,
    "Base Lot = 0.10": RULE_BASE_LOT,
    "Grid Spacing ~= 5 USD": RULE_GRID_SPACING,
    "Grid Direction (BUY down / SELL up)": RULE_GRID_DIRECTION,
    "Both-Sides Initial Exposure": RULE_BOTH_SIDES,
    "Contract Size GOLDmicro = 1.0": RULE_CONTRACT_SIZE,
    "Partial Close EXISTS (deal-level)": RULE_PARTIAL_EXISTS,
    "Normal Resume (<=2s)": RULE_NORMAL_RESUME,
    "Grid Trigger Semantics": RULE_GRID_TRIGGER,
    "Basket Trigger Semantics": RULE_BASKET_TRIGGER,
    "Partial Trigger": RULE_PARTIAL_TRIGGER,
    "Partial Volume Rule": RULE_PARTIAL_VOLUME,
    "Partial Level Rule": RULE_PARTIAL_LEVEL,
    "Emergency Mechanism": RULE_EMERGENCY,
    "Restart Recovery": RULE_RESTART_RECOVERY,
    "AccumulatorTargetUSD = 1.68 (per basket)": RULE_ACCUM_1_68,
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    status: str                      # VERIFIED / PARTIAL / UNKNOWN / REJECTED
    description: str = ""
    candidate: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    confidence: str = ""
    sample_size: str = ""
    accounts: List[str] = field(default_factory=list)
    exceptions: str = ""
    alternative_explanations: List[str] = field(default_factory=list)
    model_version: str = ""
    implemented_as_v168_behavior: bool = False


class RuleRegistry:
    """Read-only view over the frozen contract rules."""

    def __init__(self, model_version: ModelVersion, rules: List[Rule]):
        self.model_version = model_version
        self._rules: Dict[str, Rule] = {r.rule_id: r for r in rules}

    @classmethod
    def from_contract(cls, repo_root=None) -> "RuleRegistry":
        doc = load_contract(repo_root)
        mv = ModelVersion(model_id=doc["model_id"],
                          model_hash=_hash_of(repo_root))
        rules = []
        for r in rules_from_contract(doc):
            name = r["rule"]
            rules.append(Rule(
                rule_id=_RULE_NAME_MAP.get(name, name),
                name=name, status=r["status"],
                description=r.get("notes", ""),
                candidate=r.get("candidate", ""),
                evidence_refs=[e for e in r.get("evidence", "").replace(";", " ").split() if e],
                model_version=doc["model_id"],
                implemented_as_v168_behavior=r.get("implemented_as_v168_behavior", False)))
        return cls(mv, rules)

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def all(self) -> List[Rule]:
        return sorted(self._rules.values(), key=lambda r: r.rule_id)

    def by_status(self, status: str) -> List[Rule]:
        return [r for r in self.all() if r.status == status]

    def require_verified(self, rule_id: str) -> Rule:
        r = self.get(rule_id)
        if r.status != VERIFIED:
            raise RuleNotVerified(rule_id, r.status)
        return r


class RuleNotVerified(RuntimeError):
    def __init__(self, rule_id: str, status: str):
        super().__init__(
            f"rule {rule_id} is {status}, not VERIFIED — cannot be "
            f"implemented/executed as V1.68 behavior")


def _hash_of(repo_root):
    from core.our_ea.contract import _CONTRACT_RELPATH, _repo_root, _file_hash
    return _file_hash(os.path.join(repo_root or _repo_root(), _CONTRACT_RELPATH))


import os  # noqa: E402  (used by _hash_of)


# --------------------------------------------------------------------- §13
@dataclass(frozen=True)
class ModelUncertainty:
    """Emitted whenever a decision would depend on an UNKNOWN/PARTIAL rule."""
    timestamp: str
    model_version: str
    rule_id: str
    state: str
    reason: str
    required_evidence: str
    execution_mode: str
    trace_id: str

    def to_dict(self) -> dict:
        return self.__dict__


UNCERTAINTY_REQUIRED_EVIDENCE = {
    RULE_PARTIAL_TRIGGER: "controlled test or tick-level data exposing the "
                          "partial-close evaluation instant",
    RULE_PARTIAL_VOLUME: "deal-level requested-vs-filled arithmetic from a "
                         "controlled run",
    RULE_EMERGENCY: "an observed emergency event or vendor documentation of "
                    "the trigger",
    RULE_RESTART_RECOVERY: "execute TEST_R_RESTART_RECOVERY (spec in frozen "
                           "model / Phase 5.2)",
    RULE_GRID_TRIGGER: "controlled test separating previous-entry vs extreme "
                       "anchor",
    RULE_BASKET_TRIGGER: "tick-level observation of the close evaluation "
                         "instant",
    RULE_PARTIAL_LEVEL: "unambiguous position attribution (deal-level)",
}
