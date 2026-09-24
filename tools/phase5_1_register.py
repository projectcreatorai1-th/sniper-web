"""Phase 5.1: register forensic evidence + model candidates.

- Adds evidence records E011+ (OBSERVED, from 4 real XM Global accounts)
- Creates ModelCandidates (status CANDIDATE — acceptance requires a human
  reviewer; auto-confirm is forbidden by project constraints)
Idempotent: re-running skips records/candidates that already exist.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evidence import (EvidenceRecord, default_evidence_registry,
                           MT5_CSV, OBSERVED)

HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"
from core.model_candidates import ModelCandidateStore

FORENSIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "phase5_1_forensic.json")

with open(FORENSIC, "r", encoding="utf-8") as f:
    F = json.load(f)

NOW = datetime.now().isoformat(timespec="seconds")
SRC = "MT5 Trade History xlsx export (4 real accounts, XM Global, GOLDmicro)"
HASHES = "; ".join(f"{a}={d['sha256'][:16]}" for a, d in F["sources"].items())
TOTALS = (f"5,163 positions | 10,593 orders | 10,593 deals | 862 complete cycles "
          f"| 855/862 winning baskets")


def ev(eid, param, claim, value, confidence, notes):
    return EvidenceRecord(
        evidence_id=eid, source_type=MT5_CSV, source_name=SRC,
        source_reference=HASHES, claim=claim, observed_value=value,
        ea_version="1.68", parameter=param, status=OBSERVED,
        confidence=confidence, timestamp=NOW, notes=notes)


RECORDS = [
    ev("E011", "-", "Data provenance for Phase 5.1 forensic set",
       "4 accounts: 335504856/391629843/411173797/440192945 (real, Hedge, USD)",
       HIGH, TOTALS + " | " + HASHES),
    ev("E012", "LotMultiplier/BaseLot",
       "Lot progression Lot(n) = floor(0.1 * 1.1^(n-1) / 0.01) * 0.01 "
       "(truncation to lot step, NOT round-half-up)",
       "3,419/3,427 = 99.77% match; 8 exceptions confined to 391629843 "
       "Sep 23-24 lot sequence 0.12-0.30 (suspected manual parameter change)",
       HIGH, "Current SSOT lot_for_level rounds half-up and disagrees at "
       "L5/L7/L10/L12/L14+ (82.90% match). Model change requires candidate "
       "acceptance - not applied here."),
    ev("E013", "GridStepUSD",
       "Grid spacing per additional same-side entry ~5 USD",
       "n=3,426 | median 5.09 | P5 4.72 | P95 5.98 | 85.2% within [4.5, 5.5]",
       HIGH, "Spacings are market-execution distances, not exact parameter "
       "steps; median 5.09 consistent with GridStepUSD=5.0 + spread/slippage."),
    ev("E014", "Grid direction",
       "BUY grid adds LOWER, SELL grid adds HIGHER (averaging-down both sides)",
       "BUY down 1,732/1,732 = 100.00% | SELL up 1,692/1,695 = 99.82%",
       HIGH, ""),
    ev("E015", "BothSides/BaseLot",
       "Every cycle opens a BUY 0.1 + SELL 0.1 pair; base lot 0.1",
       "Both sides in first 2 entries: 857/862 = 99.4% | first-entry lot 0.1: "
       "1,715/1,719 = 99.8% | 72% of first pairs share the same second",
       HIGH, ""),
    ev("E016", "AccumTargetUSD (basket close trigger)",
       "Basket closes at an approximately FIXED dollar profit near $1.0, "
       "independent of basket size",
       "855 winners: min +0.43 | P5 +1.03 | P25 +1.10 | median +1.14 | "
       "7 near-zero losers (max -0.24, spread events)",
       HIGH, "CONTRADICTS the AccumTargetUSD=1.68 per-basket candidate: no "
       "cluster near 1.68. gross/lots ratio falls from 2.24 (lvl3) to 1.05 "
       "(lvl8) -> trigger is not per-lot. Deep grids overshoot more "
       "(lvl9 median 2.10, lvl10 3.20) due to faster P/L ticks."),
    ev("E017", "Partial close",
       "Partial closes occur mid-cycle: single positions close while the "
       "basket continues; oldest (lowest-level) volumes close first",
       "255 solo out-deal bursts (of 1,115 total close bursts); partial "
       "volumes concentrated 0.10-0.19; partial P/L median +0.24",
       MEDIUM, "860 multi-deal bursts match 862 complete cycles ~1:1 -> "
       "each cycle ends in ONE full-basket burst. Partial mechanism "
       "threshold (per closed volume ~1.68/lot hypothesis) unverified."),
    ev("E018", "Cycle resume",
       "Next cycle starts immediately (same/next second) after basket close",
       "<=2s resume: 335504856 132/132 | 391629843 401/406 | 411173797 "
       "190/190 | 440192945 134/134",
       HIGH, ""),
    ev("E019", "Contract size",
       "GOLDmicro contract size = 1 (1 lot = 1 oz; 0.1 lot moves $0.10 per $1)",
       "n=5,083 implied | median 1.0000 | stdev 0.0091 | 70.9% within 0.005",
       HIGH, "XAUUSD standard contract is 100; GOLDmicro is 100x smaller. "
       "All P/L math in observations uses contract=1."),
    ev("E020", "EA provenance",
       "All entries are EA-generated market orders with comment "
       "'CashFlow Buy'/'CashFlow Sell'; closes carry no comment",
       "in-deals with CashFlow comment: 5,184/5,184 = 100% | out-deals with "
       "comment: 0/5,609 | non-market orders: 0 | partial fills: 0",
       HIGH, ""),
    ev("E021", "EmergencyDistanceFromCycleUSD",
       "No emergency close occurred in the production window",
       "0/862 baskets closed at significant loss; worst gross -0.24 "
       "(spread event); deepest grid 32 levels, 20.07 lots, 28.1h, "
       "closed +21.80",
       MEDIUM, "Emergency behaviour remains unobserved in production; "
       "E007 (90.0) and E008 (50.0 doc) stand unchanged. Deep-grid "
       "survival data bounds the trigger: emergency did NOT fire at "
       "floating losses implied by 32-level grid."),
    ev("E022", "Restart recovery",
       "After a 7.45h pause the EA resumed with a fresh base-lot 0.1 cycle",
       "391629843: closed 2026.09.23 06:56:12 (+1.15), next cycle "
       "2026.09.23 14:23:12 starts at lot 0.1; all other gaps <=1s",
       LOW, "Single event; no controlled restart test performed."),
    ev("E023", "Parameter change anomaly",
       "Lot sequence on 391629843 Sep 23-24 (0.12/0.14/0.15/0.17 and "
       "0.18/0.20/0.22/0.25/0.27/0.30) fits neither floor nor round formula",
       "8/3,427 levels = 0.23% of all checks",
       MEDIUM, "Suspected manual parameter change (BaseLot/multiplier) "
       "during live run -> lot progression is parameter-driven, supporting "
       "the formula structure rather than contradicting it."),
    ev("E024", "Determinism",
       "All 4 accounts (same EA+params) opened/closed identical baskets at "
       "identical seconds repeatedly",
       "8 cycle-starts aligned across all 4 accounts; 31 across >=3; "
       "simultaneous close bursts e.g. 2026.09.16 21:19:52 in all 4",
       MEDIUM, "Supports deterministic signal logic (no random entries)."),
]

CANDIDATES = [
    ("LOT_FORMULA",
     "Lot(n) = floor(BaseLot * LotMultiplier^(n-1) / lot_step) * lot_step "
     "with BaseLot=0.1, LotMultiplier=1.1 (truncation, not round-half-up)",
     ["E012", "E023"], "If accepted, core/calculations.py lot_for_level "
     "rounding must change to floor; affects L5/L7/L10/L12/L14+ values."),
    ("GRID_SPACING",
     "GridStepUSD = 5.0 on GOLDmicro (median observed spacing 5.09)",
     ["E013"], "Execution noise ~ +/-0.6; P50 5.09."),
    ("GRID_DIRECTION",
     "BUY grid averages down (adds lower), SELL grid averages up "
     "(adds higher)",
     ["E014"], ""),
    ("BASKET_SCOPE",
     "Each cycle opens simultaneously with BUY 0.1 + SELL 0.1 and manages "
     "both sides independently",
     ["E015", "E020"], ""),
    ("PARTIAL_CLOSE",
     "Partial closes release the oldest grid levels mid-cycle while the "
     "cycle continues; final close is a single full-basket burst",
     ["E017"], "Threshold formula unknown; per-closed-lot ~1.68 is a "
     "hypothesis only."),
    ("CYCLE_RULE",
     "Basket closes when total profit reaches a fixed target near $1.0 "
     "(AccumTargetUSD); realized median +1.14",
     ["E016"], "CONFLICT: documentation candidate said 1.68. Observed "
     "distribution (P5 +1.03, P25 +1.10) supports ~1.0-1.1. Requires "
     "resolution before acceptance."),
    ("CYCLE_RULE",
     "After basket close the EA immediately opens the next base-lot pair "
     "(<=2s); after pause/restart it resumes at base lot",
     ["E018", "E022"], ""),
]


def main():
    reg = default_evidence_registry()
    added = skipped = 0
    for r in RECORDS:
        try:
            reg.add(r)
            added += 1
            print(f"  + {r.evidence_id} ({r.parameter})")
        except KeyError:
            skipped += 1
            print(f"  = {r.evidence_id} exists, skipped")

    store = ModelCandidateStore()
    existing = [(c.rule_type, c.description) for c in store.all()]
    for rule_type, desc, ev_ids, notes in CANDIDATES:
        if (rule_type, desc) in existing:
            print(f"  = candidate exists: {rule_type}: {desc[:50]}…")
            continue
        c = store.create(rule_type=rule_type, description=desc,
                         source_evidence_ids=ev_ids, notes=notes)
        print(f"  + {c.candidate_id} [{c.status}] {rule_type}: {desc[:60]}…")

    print(f"\nEvidence added: {added} (skipped {skipped}) | "
          f"candidates now: {len(store.all())} (all CANDIDATE — not accepted)")
    for c in store.all():
        assert c.status == "CANDIDATE", "auto-confirm forbidden!"
    print("Constraint check OK: no candidate auto-confirmed.")


if __name__ == "__main__":
    main()
