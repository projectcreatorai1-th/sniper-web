"""Restart recovery — status and future controlled-test specification.

Normal resume (basket close -> next pair <= 2s) is VERIFIED (E018).
Restart recovery is a DIFFERENT rule: behaviour after EA stop / terminal
restart / reconnect with an open basket. Production data shows exactly
one pause (7.45h on 391629843) after which the EA opened a FRESH base-lot
cycle (E022, LOW confidence single event). Inferring restart behaviour
from normal cycle transitions is forbidden -> status UNKNOWN.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

from core.forensics.cycle_reconstruction import Cycle, FMT

PAUSE_THRESHOLD_S = 60.0


def scan_pauses(cycles: Sequence[Cycle]) -> List[dict]:
    pauses = []
    for cyc in cycles:
        gap = cyc.basket_close.get("next_cycle_gap_s")
        if gap is not None and gap > PAUSE_THRESHOLD_S:
            nxt = None
            # find the cycle that follows (by start time ordering per account)
            same = [c for c in cycles
                    if c.account_id == cyc.account_id and c.start_time > cyc.end_time]
            if same:
                nxt = min(same, key=lambda c: c.start_time)
            pauses.append({
                "account_id": cyc.account_id,
                "closed_at": cyc.end_time,
                "gap_s": gap,
                "next_cycle_start": nxt.start_time if nxt else None,
                "next_cycle_first_entries": (
                    [{"side": m["side"], "volume": m["volume"],
                      "price": m["open_price"]} for m in nxt.initial_entries]
                    if nxt else []),
                "next_cycle_confidence": nxt.confidence if nxt else None,
            })
    return pauses


RESTART_TEST_SPEC = {
    "name": "TEST_R_RESTART_RECOVERY",
    "status": "NOT_EXECUTED",
    "goal": "Verify EA state restoration after stop/restart with an open basket",
    "preconditions": [
        "DEMO account only",
        "EA attached to GOLDmicro M15 with confirmed parameter set",
        "Recording: MT5 journal + trade report before/after",
    ],
    "steps": [
        "1. Let the EA open a cycle and add >= 2 grid levels on one side",
        "2. Note open positions, lots, levels, basket P/L (screenshot + report export)",
        "3. STOP the EA (remove from chart)",
        "4. Close and reopen the MT5 terminal",
        "5. Re-attach the EA with the SAME parameters",
        "6. Observe: does it adopt the existing positions (levels/lots continue "
        "the ladder) or start a new independent cycle?",
        "7. Record first N decisions until basket closes",
    ],
    "acceptance": {
        "ADOPTS_STATE": "EA references existing positions in its grid math "
        "(next add continues ladder lots, basket target counts old positions)",
        "STARTS_NEW": "EA opens a fresh 0.1/0.1 pair while old positions remain "
        "(orphaning them)",
        "MIXED": "document exact behaviour; any deviation goes to Evidence Review",
    },
    "evidence_to_capture": [
        "report export before stop", "report export after restart+close",
        "journal log", "exact timestamps",
    ],
    "claim_policy": "Until executed: RestartRecovery = UNKNOWN",
}


def restart_status(pauses: Sequence[dict]) -> dict:
    fresh_starts = sum(
        1 for p in pauses
        if p["next_cycle_first_entries"]
        and {e["side"] for e in p["next_cycle_first_entries"]} == {"BUY", "SELL"}
        and all(abs(e["volume"] - 0.10) <= 0.005
                for e in p["next_cycle_first_entries"]))
    return {
        "normal_resume": "VERIFIED (E018)",
        "restart_recovery": "UNKNOWN",
        "pauses_observed": len(pauses),
        "fresh_base_lot_after_pause": fresh_starts,
        "note": "single-event observation only (E022, LOW confidence); "
        "controlled test TEST_R_RESTART_RECOVERY required",
        "test_spec": RESTART_TEST_SPEC,
    }
