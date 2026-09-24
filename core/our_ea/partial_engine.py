"""Basket close engine (§21-§12) + partial engine (§22).

Basket trigger is PARTIAL: three compatible hypotheses from the frozen
model replay (GROSS >= 1.00 / lots x 0.50 / lots x 0.85). The engine
evaluates whichever hypotheses are configured — never declaring one
VERIFIED, never activating 1.68 (REJECTED).

Partial close: EXISTS is VERIFIED; trigger/volume UNKNOWN, level PARTIAL
-> any partial decision MUST go through uncertainty handling (§13).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

RULE_BASKET_TRIGGER = "R-BASKET-TRIGGER"
RULE_ACCUM_REJECTED = "R-ACCUM-1-68"
RULE_PARTIAL_EXISTS = "R-PARTIAL-EXISTS"
RULE_PARTIAL_TRIGGER = "R-PARTIAL-TRIGGER"
RULE_PARTIAL_VOLUME = "R-PARTIAL-VOLUME"
RULE_PARTIAL_LEVEL = "R-PARTIAL-LEVEL"

H_GROSS_1_00 = "H_GROSS_1_00"
H_PER_LOT_0_50 = "H_PER_LOT_0_50"
H_PER_LOT_0_85 = "H_PER_LOT_0_85"
COMPATIBLE_HYPOTHESES = (H_GROSS_1_00, H_PER_LOT_0_50, H_PER_LOT_0_85)
REJECTED_HYPOTHESIS = "H_GROSS_1_68"      # REJECTED — never selectable


class BasketTriggerError(ValueError):
    pass


@dataclass(frozen=True)
class BasketTriggerConfig:
    hypothesis: str = H_GROSS_1_00        # DECLARED choice, not V1.68 fact
    minimum_realized_usd: float = 0.70    # observed winners floor (P5 1.03,
                                          # spread events to 0.43) — sanity band
    def validate(self) -> None:
        if self.hypothesis not in COMPATIBLE_HYPOTHESES:
            raise BasketTriggerError(
                f"hypothesis must be one of {COMPATIBLE_HYPOTHESES} "
                f"({REJECTED_HYPOTHESIS} is REJECTED by evidence E027)")


@dataclass(frozen=True)
class BasketTriggerEvaluation:
    should_close: bool
    hypothesis_id: str
    threshold: float
    watched_value: float
    rule_ids: tuple = (RULE_BASKET_TRIGGER,)


class BasketCloseEngine:
    """Evaluates the configured close hypothesis against basket state."""

    def __init__(self, config: Optional[BasketTriggerConfig] = None):
        self.config = config or BasketTriggerConfig()
        self.config.validate()

    def threshold(self, total_lots: float) -> float:
        h = self.config.hypothesis
        if h == H_GROSS_1_00:
            return 1.00
        if h == H_PER_LOT_0_50:
            return round(total_lots * 0.50, 8)
        if h == H_PER_LOT_0_85:
            return round(total_lots * 0.85, 8)
        raise BasketTriggerError(h)

    def evaluate(self, floating_gross: float, total_lots: float,
                 realized_gross: float = 0.0) -> BasketTriggerEvaluation:
        watched = round(floating_gross + realized_gross, 8)
        thr = self.threshold(total_lots)
        return BasketTriggerEvaluation(
            should_close=watched >= thr,
            hypothesis_id=self.config.hypothesis, threshold=thr,
            watched_value=watched)


# ------------------------------------------------------------------ §22
class PartialDecisionUnavailable(RuntimeError):
    """Raised when a partial close decision is requested: trigger and
    volume rules are UNKNOWN — the caller must emit MODEL_UNCERTAINTY and
    apply OUR EA safety policy instead of guessing V1.68 behaviour."""


class PartialEngine:
    """Partial close: EXISTS VERIFIED; decisions are NOT available."""

    rule_ids = (RULE_PARTIAL_EXISTS, RULE_PARTIAL_TRIGGER,
                RULE_PARTIAL_VOLUME, RULE_PARTIAL_LEVEL)

    def exists(self) -> bool:
        return True      # R-PARTIAL-EXISTS VERIFIED (492 events, E025)

    def decide_volume(self, *args, **kwargs):
        raise PartialDecisionUnavailable(
            "PARTIAL_VOLUME is UNKNOWN (R-PARTIAL-VOLUME)")

    def decide_trigger(self, *args, **kwargs):
        raise PartialDecisionUnavailable(
            "PARTIAL_TRIGGER is UNKNOWN (R-PARTIAL-TRIGGER)")

    def decide_level(self, *args, **kwargs):
        raise PartialDecisionUnavailable(
            "PARTIAL_LEVEL is PARTIAL (390 FIFO-feasible / 102 ambiguous) — "
            "not decidable as V1.68 behaviour")
