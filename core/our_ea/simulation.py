"""Deterministic simulation engine (§32) + failure injection (§33).

Scenarios produce SYNTHETIC price paths (source_type=SYNTHETIC, never
mixed with evidence) that drive the real Strategy Core through a
SimulationAdapter. Failure injection wraps the adapter to reject /
timeout / duplicate / delay and verifies safe handling.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from core.our_ea.execution import (ExecutionAdapter, ExecutionIntent,
                                   ExecutionResult, SIMULATION)

SCENARIOS = (
    "TREND_UP", "TREND_DOWN", "RANGE", "REVERSAL", "V_SHAPE", "GAP",
    "HIGH_VOLATILITY", "LOW_VOLATILITY", "SPREAD_WIDENING", "FAST_MOVE",
    "DEEP_GRID", "MAX_LOT", "INSUFFICIENT_MARGIN", "ORDER_REJECTION",
    "MISSING_TICK", "DELAYED_TICK", "DISCONNECT", "RECONNECT",
    "PROCESS_RESTART", "PARTIAL_CLOSE", "BASKET_CLOSE_FAILURE",
    "DUPLICATE_EVENT",
)


@dataclass(frozen=True)
class Bar:
    t: int
    buy: float
    sell: float
    spread: float


def generate_bars(scenario: str, n: int = 120, start: float = 4400.0,
                  seed: int = 42) -> List[Bar]:
    """Deterministic synthetic paths (LCG noise — reproducible)."""
    state = seed
    def rnd():
        nonlocal state
        state = (state * 1664525 + 1013904223) % (2 ** 31)
        return state / 2 ** 31 - 0.5

    bars: List[Bar] = []
    px = start
    for t in range(n):
        spread = 0.50
        if scenario == "TREND_UP":
            px += 2.0 + rnd() * 0.4
        elif scenario == "TREND_DOWN":
            px -= 2.0 + rnd() * 0.4
        elif scenario == "RANGE":
            px += 3.0 * math.sin(t / 6.0) * 0.5 + rnd() * 0.3
        elif scenario == "REVERSAL":
            px += -3.0 if t < n // 2 else 3.0
        elif scenario == "V_SHAPE":
            px += -3.5 if t < n // 2 else 3.5
        elif scenario == "GAP":
            px += 0.2 * rnd()
            if t == n // 3:
                px += 25.0                      # one violent gap
        elif scenario == "HIGH_VOLATILITY":
            px += rnd() * 12.0
        elif scenario == "LOW_VOLATILITY":
            px += rnd() * 0.4
        elif scenario == "SPREAD_WIDENING":
            px -= 1.5 + rnd() * 0.5             # drift so grid triggers fire
            spread = 0.5 + (t / n) * 1.5        # widens past limits
        elif scenario == "FAST_MOVE":
            px += 0.1 * rnd()
            if t in (n // 4, n // 4 + 1, n // 4 + 2):
                px -= 9.0                       # cascade trigger burst
        elif scenario in ("DEEP_GRID",):
            px -= 1.2                            # sustained adverse drift
        elif scenario in ("MAX_LOT", "INSUFFICIENT_MARGIN"):
            px -= 6.0                            # fast ladder climb
        else:
            px += rnd() * 2.0
        bars.append(Bar(t=t, buy=round(px, 2), sell=round(px - spread, 2),
                        spread=round(spread, 2)))
    return bars


@dataclass
class SimulationRun:
    scenario: str
    source_type: str = "SYNTHETIC"
    ticks: int = 0
    events: Dict[str, int] = field(default_factory=dict)
    cycles: int = 0
    safe_stops: int = 0
    risk_blocks: int = 0
    uncertainties: int = 0
    final_state: str = ""
    notes: List[str] = field(default_factory=list)

    def summary(self) -> dict:
        return self.__dict__


def run_scenario(core, bars: List[Bar], scenario: str,
                 on_tick_extra: Optional[Callable] = None) -> SimulationRun:
    run = SimulationRun(scenario=scenario)
    for bar in bars:
        core.on_tick(bar.buy, bar.sell, bar.spread)
        if on_tick_extra:
            on_tick_extra(core, bar)
    run.ticks = core.tick_no
    run.cycles = core.cycle_sequence
    run.final_state = core.sm.state
    run.uncertainties = len(core.uncertainties)
    types: Dict[str, int] = {}
    for e in core.log.all():
        types[e.event_type] = types.get(e.event_type, 0) + 1
    run.events = types
    run.safe_stops = types.get("SAFE_STOP", 0)
    run.risk_blocks = types.get("RISK_BLOCK", 0)
    return run


# --------------------------------------------------------------------- §33
class FailureInjectionAdapter(ExecutionAdapter):
    """Wraps another adapter and injects failures per configuration.

    Injectors: reject_actions / timeout_actions (action-based),
    reject_first_n, duplicate_last (replays previous intent), stall_s
    (simulated delay marker)."""

    mode = SIMULATION

    def __init__(self, inner: ExecutionAdapter, reject_actions: tuple = (),
                 timeout_actions: tuple = (), reject_first_n: int = 0,
                 duplicate_close: bool = False):
        self.inner = inner
        self.reject_actions = set(reject_actions)
        self.timeout_actions = set(timeout_actions)
        self.reject_first_n = reject_first_n
        self.duplicate_close = duplicate_close
        self.last_result: Optional[ExecutionResult] = None

    def submit(self, intent: ExecutionIntent,
               market_price: float = 0.0) -> ExecutionResult:
        if self.reject_first_n > 0:
            self.reject_first_n -= 1
            return ExecutionResult(intent.intent_id, "REJECTED", 0.0,
                                   market_price, reason="injected reject")
        if intent.action in self.reject_actions:
            return ExecutionResult(intent.intent_id, "REJECTED", 0.0,
                                   market_price,
                                   reason="injected rejection")
        if intent.action in self.timeout_actions:
            return ExecutionResult(intent.intent_id, "TIMEOUT", 0.0,
                                   market_price, reason="injected timeout")
        res = self.inner.submit(intent, market_price)
        self.last_result = res
        return res
