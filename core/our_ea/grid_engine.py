"""Grid engine (§20) — direction VERIFIED, spacing distribution, trigger
semantics PARTIAL with configurable hypothesis_id.

Hypotheses (never a declared winner):
  H_PREV_ENTRY : next add when price crosses previous entry - step
  H_EXTREME    : ... crosses the extreme OPEN price - step
(they coincide in averaging-down ladders; H_AVG_PRICE is REJECTED.)

Every grid decision carries hypothesis_id — hard-coding either
hypothesis as *verified* is forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

RULE_DIRECTION = "R-GRID-DIRECTION"
RULE_SPACING = "R-GRID-SPACING"
RULE_TRIGGER = "R-GRID-TRIGGER"

H_PREV_ENTRY = "H_PREV_ENTRY"
H_EXTREME = "H_EXTREME"
VALID_HYPOTHESES = (H_PREV_ENTRY, H_EXTREME)

# Observed distribution (E013): median 5.09, P5 4.72, P95 5.98,
# 85.2% within [4.5, 5.5]. Kept as tolerance, not an exact constant.
OBSERVED_SPACING = {"median": 5.09, "p5": 4.72, "p95": 5.98,
                    "band": (4.5, 5.5), "band_pct": 85.2}


class GridEngineError(ValueError):
    pass


@dataclass(frozen=True)
class GridConfig:
    step_usd: float = 5.0
    tolerance_usd: float = 1.0        # observed execution scatter
    trigger_hypothesis: str = H_PREV_ENTRY

    def validate(self) -> None:
        if self.step_usd <= 0:
            raise GridEngineError("step_usd must be > 0")
        if self.trigger_hypothesis not in VALID_HYPOTHESES:
            raise GridEngineError(
                f"trigger_hypothesis must be one of {VALID_HYPOTHESES} — "
                "no hypothesis is VERIFIED; selection is a declared "
                "configuration choice, not a V1.68 fact")


@dataclass(frozen=True)
class GridDecision:
    should_add: bool
    side: str
    reference_price: float
    trigger_price: float
    market_price: float
    hypothesis_id: str
    rule_ids: tuple = (RULE_DIRECTION, RULE_SPACING, RULE_TRIGGER)


class GridEngine:
    def __init__(self, config: Optional[GridConfig] = None):
        self.config = config or GridConfig()
        self.config.validate()

    def next_add_price(self, side: str, open_prices: List[float],
                       prev_entry: Optional[float]) -> float:
        """Trigger price for the next add on `side` under the configured
        hypothesis (BUY adds BELOW, SELL adds ABOVE — R-GRID-DIRECTION)."""
        if side == "BUY":
            if self.config.trigger_hypothesis == H_PREV_ENTRY:
                anchor = prev_entry if prev_entry is not None else max(open_prices)
            else:
                anchor = min(open_prices)
            return round(anchor - self.config.step_usd, 10)
        if side == "SELL":
            if self.config.trigger_hypothesis == H_PREV_ENTRY:
                anchor = prev_entry if prev_entry is not None else min(open_prices)
            else:
                anchor = max(open_prices)
            return round(anchor + self.config.step_usd, 10)
        raise GridEngineError(f"side must be BUY/SELL, got {side}")

    def evaluate(self, side: str, market_price: float,
                 open_prices: List[float],
                 prev_entry: Optional[float]) -> GridDecision:
        trig = self.next_add_price(side, open_prices, prev_entry)
        hit = market_price <= trig if side == "BUY" else market_price >= trig
        return GridDecision(should_add=hit, side=side,
                            reference_price=trig + self.config.step_usd,
                            trigger_price=trig, market_price=market_price,
                            hypothesis_id=self.config.trigger_hypothesis)
