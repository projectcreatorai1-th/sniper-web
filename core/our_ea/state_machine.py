"""Explicit state machine (§14) — no implicit transitions.

States and transition table are declared up front; attempting an
undeclared transition raises InvalidTransition. Every performed
transition is recorded with state_before/event/condition/state_after/
reason/rule_id/model_version/trace_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

IDLE = "IDLE"
INITIALIZING = "INITIALIZING"
WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
LONG_ACTIVE = "LONG_ACTIVE"
SHORT_ACTIVE = "SHORT_ACTIVE"
BOTH_SIDES_ACTIVE = "BOTH_SIDES_ACTIVE"
GRID_ACTIVE = "GRID_ACTIVE"
PARTIAL_CLOSE_PENDING = "PARTIAL_CLOSE_PENDING"
BASKET_CLOSE_PENDING = "BASKET_CLOSE_PENDING"
CLOSING = "CLOSING"
CLOSED = "CLOSED"
PAUSED = "PAUSED"
DISCONNECTED = "DISCONNECTED"
RECOVERY = "RECOVERY"
UNCERTAIN = "UNCERTAIN"
ERROR = "ERROR"
SAFE_STOP = "SAFE_STOP"

STATES = (IDLE, INITIALIZING, WAITING_FOR_ENTRY, LONG_ACTIVE, SHORT_ACTIVE,
          BOTH_SIDES_ACTIVE, GRID_ACTIVE, PARTIAL_CLOSE_PENDING,
          BASKET_CLOSE_PENDING, CLOSING, CLOSED, PAUSED, DISCONNECTED,
          RECOVERY, UNCERTAIN, ERROR, SAFE_STOP)

# (state_before, event) -> state_after   [declared transitions only]
TRANSITIONS: Dict[Tuple[str, str], str] = {
    (IDLE, "INIT"): INITIALIZING,
    (INITIALIZING, "INIT_OK"): WAITING_FOR_ENTRY,
    (INITIALIZING, "INIT_FAIL"): ERROR,
    (WAITING_FOR_ENTRY, "OPEN_LONG"): LONG_ACTIVE,
    (WAITING_FOR_ENTRY, "OPEN_SHORT"): SHORT_ACTIVE,
    (WAITING_FOR_ENTRY, "OPEN_BOTH"): BOTH_SIDES_ACTIVE,
    (LONG_ACTIVE, "OPEN_SHORT"): BOTH_SIDES_ACTIVE,
    (SHORT_ACTIVE, "OPEN_LONG"): BOTH_SIDES_ACTIVE,
    (LONG_ACTIVE, "GRID_ADD"): GRID_ACTIVE,
    (SHORT_ACTIVE, "GRID_ADD"): GRID_ACTIVE,
    (BOTH_SIDES_ACTIVE, "GRID_ADD"): GRID_ACTIVE,
    (GRID_ACTIVE, "GRID_ADD"): GRID_ACTIVE,
    (GRID_ACTIVE, "PARTIAL_INTENT"): PARTIAL_CLOSE_PENDING,
    (BOTH_SIDES_ACTIVE, "PARTIAL_INTENT"): PARTIAL_CLOSE_PENDING,
    (PARTIAL_CLOSE_PENDING, "PARTIAL_DONE"): GRID_ACTIVE,
    (PARTIAL_CLOSE_PENDING, "PARTIAL_FAIL"): UNCERTAIN,
    (GRID_ACTIVE, "BASKET_INTENT"): BASKET_CLOSE_PENDING,
    (BOTH_SIDES_ACTIVE, "BASKET_INTENT"): BASKET_CLOSE_PENDING,
    (BASKET_CLOSE_PENDING, "CLOSE_START"): CLOSING,
    (BASKET_CLOSE_PENDING, "CLOSE_FAIL"): UNCERTAIN,
    (CLOSING, "CLOSED_ALL"): CLOSED,
    (CLOSING, "CLOSE_FAIL"): UNCERTAIN,
    (CLOSED, "RESUME_NEW_CYCLE"): WAITING_FOR_ENTRY,
    (CLOSED, "CYCLE_STOP"): IDLE,
    (UNCERTAIN, "RESOLVED_SAFE"): SAFE_STOP,
    (UNCERTAIN, "RESOLVED_CONTINUE"): GRID_ACTIVE,
    (UNCERTAIN, "BASKET_INTENT"): BASKET_CLOSE_PENDING,
    (UNCERTAIN, "GRID_ADD"): GRID_ACTIVE,
    (BOTH_SIDES_ACTIVE, "ALL_ENTRIES_FAILED"): WAITING_FOR_ENTRY,
    (GRID_ACTIVE, "ALL_ENTRIES_FAILED"): WAITING_FOR_ENTRY,
    (PAUSED, "RESUME"): WAITING_FOR_ENTRY,
    # safety events valid from any active state:
    **{(s, "DISCONNECT"): DISCONNECTED for s in STATES if s not in
       (DISCONNECTED, SAFE_STOP)},
    **{(s, "SAFE_STOP"): SAFE_STOP for s in STATES if s != SAFE_STOP},
}


class InvalidTransition(RuntimeError):
    pass


@dataclass(frozen=True)
class Transition:
    state_before: str
    event: str
    condition: str
    state_after: str
    reason: str
    rule_id: str
    model_version: str
    trace_id: str


class StateMachine:
    def __init__(self, model_version: str, initial: str = IDLE):
        if initial not in STATES:
            raise ValueError(f"unknown state {initial}")
        self.model_version = model_version
        self.state = initial
        self.history: List[Transition] = []

    def can(self, event: str) -> bool:
        return (self.state, event) in TRANSITIONS

    def transition(self, event: str, *, condition: str = "", reason: str = "",
                   rule_id: str = "", trace_id: str = "") -> str:
        key = (self.state, event)
        if key not in TRANSITIONS:
            raise InvalidTransition(
                f"implicit/undeclared transition rejected: "
                f"{self.state} --{event}--> ?")
        target = TRANSITIONS[key]
        self.history.append(Transition(
            state_before=self.state, event=event, condition=condition,
            state_after=target, reason=reason, rule_id=rule_id,
            model_version=self.model_version, trace_id=trace_id))
        self.state = target
        return target

    def snapshot(self) -> dict:
        return {"state": self.state, "transitions": len(self.history),
                "model_version": self.model_version}
