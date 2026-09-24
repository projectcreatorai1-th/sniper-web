"""Risk Guard (§25-§26) — OUR_EA_POLICY, entirely separate from the
V1.68 model. Every limit is configurable and traced as SOURCE=OUR_EA_POLICY.

Emergency here is OUR_EA_EMERGENCY_POLICY (max drawdown / grid depth /
margin / kill switch) — the V1.68 emergency mechanism is UNKNOWN and is
never implemented under its name.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

SOURCE_OUR_EA_POLICY = "OUR_EA_POLICY"


class RiskGuardError(ValueError):
    pass


@dataclass(frozen=True)
class RiskLimits:
    max_positions: int = 12
    max_grid_depth: int = 12
    max_total_lot: float = 2.0
    max_loss_usd: float = 50.0
    max_drawdown_pct: float = 30.0
    max_margin_usage_pct: float = 50.0
    max_spread_usd: float = 0.60
    max_slippage_usd: float = 0.50
    max_execution_time_s: float = 5.0
    session_limit: str = ""            # e.g. 'server 01:00-23:00'
    allowed_symbols: tuple = ("GOLDmicro",)
    # OUR_EA_POLICY v1.1 additions (Phase 8, change-classified MAJOR):
    max_consecutive_failures: int = 3      # order failures in a row
    max_tick_volatility_usd: float = 25.0  # per-tick move guard

    def validate(self) -> None:
        problems = []
        if self.max_positions < 1:
            problems.append("max_positions >= 1")
        if self.max_grid_depth < 1:
            problems.append("max_grid_depth >= 1")
        if self.max_total_lot <= 0:
            problems.append("max_total_lot > 0")
        if not (0 < self.max_margin_usage_pct <= 100):
            problems.append("max_margin_usage_pct in (0,100]")
        if self.max_consecutive_failures < 1:
            problems.append("max_consecutive_failures >= 1")
        if self.max_tick_volatility_usd <= 0:
            problems.append("max_tick_volatility_usd > 0")
        if problems:
            raise RiskGuardError(f"RiskLimits invalid: {'; '.join(problems)}")


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    violations: List[str] = field(default_factory=list)
    emergency_stop: bool = False
    source: str = SOURCE_OUR_EA_POLICY


@dataclass
class RiskState:
    equity_peak: float = 0.0
    balance: float = 0.0
    equity: float = 0.0
    kill_switch: bool = False
    consecutive_failures: int = 0
    last_price: float = 0.0


class RiskGuard:
    """Checks intents BEFORE execution (Strategy -> RiskGuard -> Adapter)."""

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.limits.validate()
        self.state = RiskState()

    # -- intent gating --------------------------------------------------
    def check_entry(self, *, open_positions: int, side_levels: int,
                    total_lot_after: float, spread_usd: float,
                    symbol: str = "GOLDmicro") -> RiskDecision:
        v = []
        if symbol not in self.allowed(symbol):
            v.append(f"symbol {symbol} not allowed")
        if open_positions + 1 > self.limits.max_positions:
            v.append(f"max_positions {self.limits.max_positions}")
        if side_levels + 1 > self.limits.max_grid_depth:
            v.append(f"max_grid_depth {self.limits.max_grid_depth}")
        if total_lot_after > self.limits.max_total_lot:
            v.append(f"max_total_lot {self.limits.max_total_lot}")
        if spread_usd > self.limits.max_spread_usd:
            v.append(f"max_spread {self.limits.max_spread_usd}")
        if self.state.kill_switch:
            v.append("manual kill switch engaged")
        return RiskDecision(allowed=not v, violations=v)

    def check_margin(self, margin_used: float, equity: float) -> RiskDecision:
        v = []
        if equity <= 0:
            v.append("non-positive equity")
        else:
            usage = margin_used / equity * 100.0
            if usage > self.limits.max_margin_usage_pct:
                v.append(f"max_margin_usage {usage:.1f}%")
        return RiskDecision(allowed=not v, violations=v)

    def check_drawdown(self, equity: float) -> RiskDecision:
        v = []
        if equity > self.state.equity_peak:
            self.state.equity_peak = equity
        elif self.state.equity_peak > 0:
            dd = (self.state.equity_peak - equity) / self.state.equity_peak * 100.0
            if dd > self.limits.max_drawdown_pct:
                v.append(f"max_drawdown {dd:.1f}%")
        return RiskDecision(allowed=not v, violations=v)

    def check_loss(self, floating_usd: float) -> RiskDecision:
        v = []
        stop = False
        if floating_usd < -abs(self.limits.max_loss_usd):
            v.append(f"max_loss {self.limits.max_loss_usd}")
            stop = True
        return RiskDecision(allowed=not v, violations=v,
                            emergency_stop=stop)

    # -- OUR EA emergency policy (NOT V1.68) -----------------------------
    def emergency_policy(self, *, floating_usd: float, equity: float,
                         grid_depth: int, margin_used: float) -> RiskDecision:
        v = []
        stop = False
        if floating_usd < -abs(self.limits.max_loss_usd):
            v.append("loss limit")
            stop = True
        if self.state.equity_peak > 0 and equity < self.state.equity_peak * (
                1 - self.limits.max_drawdown_pct / 100.0):
            v.append("drawdown limit")
            stop = True
        if grid_depth > self.limits.max_grid_depth:
            v.append("grid depth limit")
            stop = True
        if equity > 0 and margin_used / equity * 100.0 > self.limits.max_margin_usage_pct:
            v.append("margin limit")
            stop = True
        return RiskDecision(allowed=not stop, violations=v,
                            emergency_stop=stop)

    # ---- Phase 8 additions (OUR_EA_POLICY v1.1) ------------------------
    def record_order_failure(self) -> RiskDecision:
        """Consecutive order failures -> block until operator reset."""
        self.state.consecutive_failures += 1
        blocked = (self.state.consecutive_failures
                   >= self.limits.max_consecutive_failures)
        return RiskDecision(
            allowed=not blocked,
            violations=[f"consecutive_failures "
                        f"{self.state.consecutive_failures}"] if blocked else [])

    def record_order_success(self) -> None:
        self.state.consecutive_failures = 0

    def check_tick_volatility(self, price: float) -> RiskDecision:
        """Extreme single-tick move -> block new entries this tick."""
        v = []
        if self.state.last_price:
            move = abs(price - self.state.last_price)
            if move > self.limits.max_tick_volatility_usd:
                v.append(f"tick volatility {move:.1f} > "
                         f"{self.limits.max_tick_volatility_usd}")
        self.state.last_price = price
        return RiskDecision(allowed=not v, violations=v)

    def engage_kill_switch(self) -> None:
        self.state.kill_switch = True

    def allowed(self, symbol: str) -> tuple:
        return self.limits.allowed_symbols

    def snapshot(self) -> dict:
        return {"limits": self.limits.__dict__, "state": self.state.__dict__,
                "source": SOURCE_OUR_EA_POLICY}
