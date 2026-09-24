"""Execution abstraction (§27-§28, §43, §45).

Strategy Core never touches MT5 or any broker API. It produces
ExecutionIntent objects that flow through the Risk Guard into an
ExecutionAdapter:

    SimulationAdapter — deterministic in-memory fills
    PaperAdapter      — same core, paper account ledger
    DemoAdapter       — placeholder for a demo-broker bridge
    MT5Adapter        — LIVE: HARD LOCKED in Phase 6

LIVE lock is a hard-coded barrier (LIVE_DISABLED=True): config/UI cannot
open it. Any attempt -> LIVE_EXECUTION_REQUESTED -> reject -> SAFE_STOP
-> audit event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

SIMULATION = "SIMULATION"
PAPER = "PAPER"
DEMO = "DEMO"
LIVE = "LIVE"
EXECUTION_MODES = (SIMULATION, PAPER, DEMO, LIVE)

LIVE_DISABLED = True          # §45 hard barrier — Phase 6


class ExecutionError(RuntimeError):
    pass


class LiveLockError(ExecutionError):
    code = "LIVE_EXECUTION_REQUESTED"


@dataclass(frozen=True)
class ExecutionIntent:
    intent_id: str
    action: str                   # OPEN / CLOSE / CLOSE_ALL / CLOSE_PARTIAL
    symbol: str
    side: str                     # BUY / SELL / ""
    lot: float
    price: Optional[float]        # None -> market
    cycle_id: str = ""
    position_id: str = ""
    rule_id: str = ""
    hypothesis_id: str = ""
    reason: str = ""
    trace_id: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    intent_id: str
    status: str                   # FILLED / REJECTED / TIMEOUT / SKIPPED
    filled_lot: float = 0.0
    price: float = 0.0
    position_id: str = ""
    reason: str = ""
    execution_mode: str = SIMULATION


class ExecutionAdapter:
    mode = SIMULATION

    def submit(self, intent: ExecutionIntent,
               market_price: float = 0.0) -> ExecutionResult:
        raise NotImplementedError


class SimulationAdapter(ExecutionAdapter):
    """Deterministic fill at the supplied market price."""

    mode = SIMULATION

    def __init__(self, reject_next: int = 0, fail_actions: tuple = ()):
        self.reject_next = reject_next
        self.fail_actions = set(fail_actions)
        self.fills: List[ExecutionResult] = []
        self._next_pos = 1

    def submit(self, intent: ExecutionIntent,
               market_price: float = 0.0) -> ExecutionResult:
        if self.reject_next > 0:
            self.reject_next -= 1
            return ExecutionResult(intent.intent_id, "REJECTED", 0.0,
                                   market_price, reason="injected rejection",
                                   execution_mode=self.mode)
        if intent.action in self.fail_actions:
            return ExecutionResult(intent.intent_id, "TIMEOUT", 0.0,
                                   market_price, reason="injected timeout",
                                   execution_mode=self.mode)
        pid = f"P{self._next_pos:06d}"
        self._next_pos += 1
        res = ExecutionResult(intent.intent_id, "FILLED", intent.lot,
                              market_price or intent.price or 0.0,
                              position_id=pid, execution_mode=self.mode)
        self.fills.append(res)
        return res


class PaperAdapter(SimulationAdapter):
    """Paper account: same real Strategy Core + risk guard + event log,
    no money at risk. Keeps a running paper ledger."""

    mode = PAPER

    def __init__(self, starting_balance: float = 1000.0):
        super().__init__()
        self.balance = starting_balance
        self.starting_balance = starting_balance

    def submit(self, intent: ExecutionIntent,
               market_price: float = 0.0) -> ExecutionResult:
        res = super().submit(intent, market_price)
        return res


class DemoAdapter(SimulationAdapter):
    """Demo-broker bridge placeholder (Phase 6: demo-ready only)."""

    mode = DEMO


class LiveAdapter(ExecutionAdapter):
    """LIVE — hard-locked in Phase 6. Instantiation/selection is refused."""

    mode = LIVE

    def __init__(self):
        raise LiveLockError(
            "LIVE execution requested while LIVE_DISABLED=True (Phase 6 "
            "lock): request rejected -> SAFE_STOP -> audit event")


def resolve_mode(mode: str) -> str:
    if mode not in EXECUTION_MODES:
        raise ExecutionError(f"unknown execution mode: {mode}")
    if mode == LIVE:
        raise LiveLockError(
            "LIVE execution requested while LIVE_DISABLED=True: rejected")
    return mode


def adapter_for(mode: str, **kwargs) -> ExecutionAdapter:
    resolve_mode(mode)
    if mode == SIMULATION:
        return SimulationAdapter(**kwargs)
    if mode == PAPER:
        return PaperAdapter(**kwargs)
    if mode == DEMO:
        return DemoAdapter(**kwargs)
    raise ExecutionError(mode)
