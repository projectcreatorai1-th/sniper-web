"""Phase 5.3 — OWNER HUMAN CONFIRMATION execution.

Applies the project owner's review decisions (2026-09-24, PROJECT_OWNER)
to the candidate registry with a full audit trail. No decision is
invented here: every action maps 1:1 to the owner's written instructions.

Owner decisions applied:
  CONFIRM  : MC-001, MC-002, MC-003, MC-004, MC-007, MC-008, MC-009*
             (*MC-009 only the PARTIAL_EXISTS aspect; TRIGGER/VOLUME_RULE
              stay UNKNOWN, LEVEL_RULE stays PARTIAL)
  SUPERSEDE: MC-005 -> MC-009 (obsolete description, kept for history)
  PARTIAL  : MC-006 (basket trigger) — stays CANDIDATE; owner confirmed
             only the "+$1 domain" observation; 1.68 REJECTED as V1.68
             behavior; no exact trigger promoted to verified
  Assumption registry: lot formula/normalization/direction/both-sides
             elevated to OBSERVED_FROM_TESTING with evidence references
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.model_candidates import ModelCandidateStore
from core.assumptions import (AssumptionRegistry, OBSERVED_FROM_TESTING)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
REVIEWER = "PROJECT_OWNER"
TS = datetime.now().isoformat(timespec="seconds")
REASON_DOC = "Owner review 2026-09-24 (Phase 5.3 decision document)"

ACCEPT = {
    "MC-001": "Lot floor ladder confirmed: floor(BaseLot*Mult^(n-1)/step)*step; "
              "old round-based SSOT INVALID (4451/4451 clean-cycle checks, E012/E028)",
    "MC-002": "Grid spacing ~5 USD confirmed WITH observed distribution and "
              "tolerance preserved (median 5.09, E013) — not promoted to exact 5.0000",
    "MC-003": "BUY adds DOWN / SELL adds UP confirmed (100.00%/99.82%, E014)",
    "MC-004": "Both-sides initial exposure confirmed at OBSERVED 99.4% — "
              "exceptions retained for audit, not rounded to 100% (E015)",
    "MC-007": "Normal resume VERIFIED per owner instruction; restart recovery "
              "remains UNKNOWN and separate (E018/E022)",
    "MC-008": "Base lot = 0.10 confirmed (99.8% of first entries, E015)",
    "MC-009": "PARTIAL_EXISTS = VERIFIED only. TRIGGER=UNKNOWN, "
              "VOLUME_RULE=UNKNOWN, LEVEL_RULE=PARTIAL remain unchanged (E025)",
}

SUPERSEDE = {
    "MC-005": "Obsolete description (position-level burst interpretation) — "
              "superseded by MC-009 (deal-level intra-position analysis, E025)",
}

ASSUMPTION_UPDATES = [
    ("LOT_FORMULA_ASSUMPTION_001",
     "Confirmed by owner MC-001: BaseLot x LotMultiplier^(n-1) observed on "
     "4 real accounts, 812 HIGH-confidence cycles (E012, E028)"),
    ("LOT_NORMALIZATION_ASSUMPTION_001",
     "Confirmed by owner MC-001: normalization is FLOOR to lot step "
     "(not round); 100.00% clean-cycle match (E012, E028)"),
    ("GRID_DIRECTION_ASSUMPTION_001",
     "Confirmed by owner MC-003: BUY 100.00% down, SELL 99.82% up (E014)"),
    ("BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001",
     "Confirmed by owner MC-004: 99.4% observed, 5 exception cycles "
     "retained for audit (E015)"),
]


def main():
    store = ModelCandidateStore()
    audit = {"reviewer": REVIEWER, "timestamp": TS,
             "source": "Phase 5.3 owner decision document",
             "actions": []}

    for cid, reason in ACCEPT.items():
        try:
            c = store.accept(cid, reviewed_by=REVIEWER, note=reason)
            audit["actions"].append({
                "candidate_id": cid, "previous_status": "CANDIDATE",
                "new_status": c.status, "reviewer": REVIEWER,
                "timestamp": TS, "reason": reason,
                "evidence_refs": c.source_evidence_ids})
            print(f"  ACCEPT {cid}: {reason[:70]}…")
        except ValueError as e:
            audit["actions"].append({
                "candidate_id": cid, "action": "ACCEPT-FAILED",
                "reason": str(e), "timestamp": TS})
            print(f"  !! {cid}: {e}")

    for cid, reason in SUPERSEDE.items():
        try:
            c = store.supersede(cid, reviewed_by=REVIEWER, note=reason)
            audit["actions"].append({
                "candidate_id": cid, "previous_status": "CANDIDATE",
                "new_status": c.status, "reviewer": REVIEWER,
                "timestamp": TS, "reason": reason,
                "superseded_by": "MC-009"})
            print(f"  SUPERSEDE {cid} -> MC-009")
        except ValueError as e:
            audit["actions"].append({
                "candidate_id": cid, "action": "SUPERSEDE-FAILED",
                "reason": str(e), "timestamp": TS})
            print(f"  !! {cid}: {e}")

    # MC-006: owner confirmed ONLY the "+$1 domain" observation; the exact
    # trigger stays PARTIAL. No store mutation — record the decision.
    audit["actions"].append({
        "candidate_id": "MC-006", "previous_status": "CANDIDATE",
        "new_status": "CANDIDATE (rule-level: PARTIAL)",
        "reviewer": REVIEWER, "timestamp": TS,
        "reason": "Owner confirmed observed basket-close domain ~= +$1 only. "
                  "AccumulatorTargetUSD=1.68 REJECTED as V1.68 behavior "
                  "(90.70% violations, E027). No exact value (incl. 1.00) "
                  "promoted to verified. Compatible hypotheses retained in "
                  "registry.",
        "evidence_refs": ["E016", "E027"]})
    print("  RECORD MC-006 decision (stays PARTIAL, 1.68 REJECTED)")

    # assumption registry updates (persisted evidence-based overrides)
    areg = AssumptionRegistry(os.path.join(DATA, "assumption_overrides.json"))
    for aid, evidence in ASSUMPTION_UPDATES:
        prev = areg.get(aid).status
        areg.set_status(aid, OBSERVED_FROM_TESTING, evidence)
        audit["actions"].append({
            "assumption_id": aid, "previous_status": prev,
            "new_status": OBSERVED_FROM_TESTING, "reviewer": REVIEWER,
            "timestamp": TS, "reason": REASON_DOC, "evidence": evidence})
        print(f"  ASSUMPTION {aid}: {prev} -> {OBSERVED_FROM_TESTING}")

    out = os.path.join(DATA, "phase5_3_confirmation_audit.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out}")

    for c in store.all():
        print(f"  {c.candidate_id}: {c.status}")


if __name__ == "__main__":
    main()
