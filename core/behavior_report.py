"""BEHAVIOR_VERIFICATION_REPORT builder (Phase 2).

Assembles the 15 required sections from REAL data only:
environment / session / parameters / observed events / grid / lot /
buy-sell / basket / partial / emergency / cycle timeline / model
comparison / mismatches / unknowns / evidence / assumptions.

Nothing here computes a formula - comparators call core, registries are
read from their single sources.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core.assumptions import default_registry
from core.behavior_comparators import (
    INSUFFICIENT_DATA,
    MISMATCH,
    UNKNOWN,
    run_all_comparators,
)
from core.config import EAConfig
from core.cycle import build_cycle_timelines
from core.environment import observed_test_environment
from core.evidence import default_evidence_registry
from core.model_rules import SimulationModelRules
from core.mt5_adapters import BehaviorRecord
from core.observation import CONTROLLED_TEST_PLANS, ObservationSession
from core.param_facts import find_fact
from core.symbol_profile import SymbolProfile

SCHEMA = "SNIPER_BEHAVIOR_VERIFICATION_REPORT_V1"
DISCLAIMER = ("Behavior verification compares OBSERVED MT5 data against the "
              "SIMULATION MODEL. MATCH results are consistency observations, "
              "never proof of internal EA logic. Performance data never "
              "verifies formulas.")


def build_behavior_report(session: ObservationSession,
                          profile: Optional[SymbolProfile] = None,
                          rules: Optional[SimulationModelRules] = None) -> dict:
    profile = profile or SymbolProfile()
    rules = rules or SimulationModelRules()
    config = EAConfig.from_dict(session.parameters or EAConfig().to_dict())
    records: List[BehaviorRecord] = session.events

    comparison = run_all_comparators(records, config, profile, rules,
                                     evidence_ids=[f"session:{session.session_id}"])
    timelines = build_cycle_timelines(records)

    checks = comparison["checks"] + [{
        "check_id": "LOT-SUMMARY", "title": "Lot progression summary",
        "status": comparison["lot"]["summary"]}]
    mismatches = [c for c in checks if c.get("status") == MISMATCH]
    unknowns = [c for c in checks if c.get("status") in (UNKNOWN, INSUFFICIENT_DATA)]

    # assumption traceability: every id referenced by any check
    assumption_ids: List[str] = []
    for c in comparison["checks"]:
        assumption_ids.extend(c.get("assumption_ids", []))
    assumption_ids.extend(comparison["lot"]["assumption_ids"])
    assumption_ids = list(dict.fromkeys(assumption_ids))
    areg = default_registry()

    # evidence traceability: session + comparator references that exist
    ereg = default_evidence_registry()
    known_ids = {r.evidence_id for r in ereg.all()}
    ev_ids = [f"session:{session.session_id}"]
    for c in comparison["checks"]:
        for eid in c.get("evidence_ids", []):
            if eid.startswith("session:") or eid in known_ids:
                ev_ids.append(eid)
    ev_ids = list(dict.fromkeys(ev_ids))

    env = observed_test_environment()
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        # 1 Environment
        "environment": {
            "session_environment": {
                "environment_profile_id": session.environment_profile_id,
                "platform": None if not session.source_type else "MT5 (assumed from source)",
                "broker": session.broker or None,
                "account_type": session.account_type or None,
                "symbol": session.symbol or None,
                "timeframe": session.timeframe or None,
            },
            "observed_test_environment": env.to_dict(),
            "note": "session fields left empty are UNKNOWN",
        },
        # 2 Session
        "session": session.to_dict(),
        # 3 Parameters
        "parameters": {
            "config": config.to_dict(),
            "emergency_distance_records": [
                {"kind": v.kind, "value": v.value, "status": v.status,
                 "source": v.source, "evidence_id": v.evidence_id}
                for v in find_fact("PARAM_18").value_records],
            "parameter_21": {"status": "UNKNOWN",
                             "candidate_code_name": "AccumTargetUSD",
                             "mapping": "UNVERIFIED CANDIDATE"},
        },
        # 4 Observed events
        "observed_events": {
            "total": len(records),
            "by_event": session.event_summary(),
            "unknown_event_count": session.event_summary().get("UNKNOWN", 0),
            "cost_fields_present": {
                "commission": sum(1 for r in records if r.commission is not None),
                "swap": sum(1 for r in records if r.swap is not None),
                "spread": sum(1 for r in records if r.spread is not None),
            },
        },
        # 5-10 comparator sections
        "grid_behavior": [c for c in comparison["checks"] if c["check_id"].startswith("GRID")],
        "lot_behavior": comparison["lot"],
        "buy_sell_behavior": [c for c in comparison["checks"] if c["check_id"].startswith("BS-")],
        "basket_behavior": [c for c in comparison["checks"] if c["check_id"].startswith("BASKET")],
        "partial_close": [c for c in comparison["checks"] if c["check_id"].startswith("PARTIAL")],
        "emergency": [c for c in comparison["checks"] if c["check_id"].startswith("EMG")],
        # 11 Cycle timeline
        "cycle_timeline": {
            "cycle_count": len(timelines),
            "complete": sum(1 for t in timelines if t["status"] == "COMPLETE"),
            "incomplete": sum(1 for t in timelines if t["status"] == "INCOMPLETE"),
            "timelines": timelines,
        },
        # 12 Model comparison
        "model_comparison": {
            "counts": comparison["counts"],
            "statuses_supported": ["MATCH", "PARTIAL_MATCH", "MISMATCH",
                                   "UNKNOWN", "INSUFFICIENT_DATA"],
            "auto_correction": "DISABLED - model changes require explicit "
                               "human confirmation + new ModelVersion",
        },
        # 13 Mismatches
        "mismatches": mismatches,
        # 14 Unknowns
        "unknowns": unknowns,
        # 15 Evidence + assumptions traceability
        "evidence": {
            "ids": ev_ids,
            "records": [ereg.get(e).to_dict() for e in ev_ids
                        if not e.startswith("session:") and e in known_ids],
        },
        "assumptions": {
            "ids": assumption_ids,
            "details": areg.describe(assumption_ids),
        },
        "controlled_test_plans": CONTROLLED_TEST_PLANS,
    }
