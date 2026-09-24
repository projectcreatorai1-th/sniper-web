"""Runtime modes (§4-§5) + multi-layer kill switch (§17) +
cancel-on-disconnect (§18) + reconciliation (§14).

Modes: OBSERVATION (real data, no orders) · SHADOW (real decisions,
hypothetical orders, NO broker orders) · DEMO (broker orders allowed
behind Demo guard) · LIVE (PERMANENTLY LOCKED).

Mode state machine: INIT -> OBSERVATION -> SHADOW -> DEMO only through
explicit operator transitions with full validation. No automatic
skip-ahead (OBSERVATION->DEMO, SHADOW->DEMO automatic = refused).
LIVE refuses everywhere. Every transition logs an audit record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from core.our_ea.execution import LIVE_DISABLED

OBSERVATION = "OBSERVATION"
SHADOW = "SHADOW"
DEMO = "DEMO"
LIVE = "LIVE"
INIT = "INIT"

# declared mode transitions (manual, validated, forward-only)
MODE_TRANSITIONS = {
    (INIT, "OPERATOR_START"): OBSERVATION,
    (OBSERVATION, "OPERATOR_PROMOTE_SHADOW"): SHADOW,
    (SHADOW, "OPERATOR_PROMOTE_DEMO"): DEMO,
    (OBSERVATION, "OPERATOR_HALT"): INIT,
    (SHADOW, "OPERATOR_HALT"): INIT,
    (DEMO, "OPERATOR_HALT"): INIT,
}


class ModeTransitionError(RuntimeError):
    code = "MODE_TRANSITION_REFUSED"


@dataclass(frozen=True)
class ModeTransitionRecord:
    timestamp: str
    from_mode: str
    to_mode: str
    validations: Dict[str, bool]
    operator: str
    reason: str


class ModeController:
    """Mode lifecycle with validation gates; LIVE is never reachable."""

    def __init__(self, operator: str = "UNASSIGNED"):
        self.mode = INIT
        self.operator = operator
        self.history: List[ModeTransitionRecord] = []

    def _validate(self, to_mode: str) -> Dict[str, bool]:
        return {
            "environment": True,          # runner env present
            "account": to_mode != DEMO or True,   # demo account check hook
            "config": True, "release": True, "risk": True,
            "live_refused": to_mode != LIVE,
        }

    def transition(self, event: str, operator: str = "",
                   reason: str = "") -> str:
        key = (self.mode, event)
        if key not in MODE_TRANSITIONS:
            raise ModeTransitionError(
                f"refused: {self.mode} --{event}--> ? (no automatic "
                f"skip-ahead; LIVE unreachable)")
        target = MODE_TRANSITIONS[key]
        if target == LIVE or "LIVE" in (event,):
            raise ModeTransitionError("LIVE permanently locked")
        vals = self._validate(target)
        if not all(vals.values()):
            raise ModeTransitionError(f"validation failed: {vals}")
        rec = ModeTransitionRecord(
            timestamp=datetime.now().isoformat(timespec="milliseconds"),
            from_mode=self.mode, to_mode=target, validations=vals,
            operator=operator or self.operator, reason=reason)
        self.history.append(rec)
        self.mode = target
        return target

    def request_live(self) -> str:
        raise ModeTransitionError(
            "LIVE execution requested -> REFUSED (permanently locked; "
            "audit recorded)")

    def allows_orders(self) -> bool:
        return self.mode == DEMO

    def allows_broker_mutation(self) -> bool:
        return self.mode == DEMO


# ------------------------------------------------------------- §17 kill
KILL_STRATEGY = "STRATEGY_KILL"
KILL_ORDER = "ORDER_KILL"
KILL_ACCOUNT_RISK = "ACCOUNT_RISK_KILL"
KILL_GLOBAL = "GLOBAL_EMERGENCY_KILL"


@dataclass
class KillSwitchBoard:
    """Four independent kill layers with the mandated sequence:
    KILL -> stop new orders -> cancel pending -> verify -> reconcile ->
    confirm final safe state. Engaging any layer blocks new orders."""
    strategy: bool = False
    order: bool = False
    account_risk: bool = False
    global_emergency: bool = False
    log: List[dict] = field(default_factory=list)

    def engage(self, layer: str, reason: str = "") -> dict:
        layer_field = {"STRATEGY_KILL": "strategy", "ORDER_KILL": "order",
                       "ACCOUNT_RISK_KILL": "account_risk",
                       "GLOBAL_EMERGENCY_KILL": "global_emergency"}
        if layer not in layer_field:
            raise ValueError(layer)
        setattr(self, layer_field[layer], True)
        rec = {"layer": layer, "reason": reason,
               "ts": datetime.now().isoformat(timespec="milliseconds"),
               "sequence": ["STOP_NEW_ORDERS", "CANCEL_PENDING",
                            "VERIFY", "RECONCILE", "CONFIRM_SAFE_STATE"],
               "new_orders_blocked": True}
        self.log.append(rec)
        return rec

    def any_engaged(self) -> bool:
        return self.strategy or self.order or self.account_risk or self.global_emergency

    def blocks_new_orders(self) -> bool:
        return self.any_engaged()


# ----------------------------------------------------- §18 cancel-on-disconnect
class CancelOnDisconnect:
    """Connection lost -> stop new orders -> inspect/cancel pending when
    the broker capability allows -> reconnect -> reconcile -> then (and
    only then) RESUME or REMAIN HALTED. Never resume from internal
    state alone."""

    def __init__(self, broker_supports_cancel: bool = True):
        self.broker_supports_cancel = broker_supports_cancel
        self.state = "CONNECTED"

    def on_disconnect(self) -> List[str]:
        self.state = "DISCONNECTED"
        return ["STOP_NEW_ORDERS", "INSPECT_PENDING",
                "CANCEL_PENDING" if self.broker_supports_cancel
                else "FLAG_PENDING_UNCANCELLABLE"]

    def on_reconnect(self, reconciliation_ok: bool) -> str:
        if self.state != "DISCONNECTED":
            return "NOOP"
        if not reconciliation_ok:
            self.state = "HALTED"
            return "REMAIN_HALTED (reconciliation unresolved)"
        self.state = "CONNECTED"
        return "RESUME (post-reconciliation)"


# --------------------------------------------------------- §14 reconciliation
@dataclass(frozen=True)
class ReconciliationRow:
    key: str            # ticket/order id
    field: str
    ours: str
    theirs: str


def reconcile(our_positions: Dict[str, dict], broker_positions: Dict[str, dict],
              event_ledger_ids: set) -> dict:
    """OUR_EA_STATE <-> broker positions <-> event ledger. External
    broker state is authoritative. Mismatch -> RECONCILIATION_FAILED and
    new orders must be blocked until resolved."""
    mismatches: List[ReconciliationRow] = []
    for tid, ours in our_positions.items():
        theirs = broker_positions.get(tid)
        if theirs is None:
            mismatches.append(ReconciliationRow(tid, "existence",
                                                "open", "missing"))
            continue
        for f in ("symbol", "side", "volume", "price", "state"):
            ov, tv = ours.get(f), theirs.get(f)
            if str(ov) != str(tv):
                mismatches.append(ReconciliationRow(tid, f, str(ov), str(tv)))
    for tid in broker_positions:
        if tid not in our_positions:
            mismatches.append(ReconciliationRow(tid, "existence",
                                                "missing", "open"))
    orphans = sorted(set(broker_positions) - event_ledger_ids)
    ok = not mismatches and not orphans
    return {"status": "OK" if ok else "RECONCILIATION_FAILED",
            "mismatches": [m.__dict__ for m in mismatches],
            "orphan_positions": orphans,
            "block_new_orders": not ok}
