"""Basket engine forensics — reconstruct every basket and replay
candidate close-trigger hypotheses against historical data.

Hypotheses replayed (each scored by violation + overshoot error):
  H_GROSS_1_00 : close when gross profit >= $1.00
  H_GROSS_1_10 : ... >= $1.10
  H_GROSS_1_68 : ... >= $1.68   (documented AccumTargetUSD candidate)
  H_NET_1_00   : close when net (gross+comm+swap) >= $1.00
  H_PER_LOT_x  : profit >= total_lots * k for k in {0.5, 0.85, 1.68}

Error reporting per hypothesis:
  violations      baskets closing BELOW threshold (model would not have fired)
  overshoot_mean  mean realized profit above threshold among firings
  mae             mean absolute error vs realized close values

Conclusion statuses: BasketAmount = OBSERVED, BasketTrigger = UNKNOWN or
PARTIAL (whenever several hypotheses remain compatible). Hard-coding any
single value as "the verified trigger" is forbidden.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Sequence

from core.forensics.cycle_reconstruction import Cycle, FMT

BURST_GAP_S = 5.0


def burst_gap_seconds() -> float:
    return BURST_GAP_S


@dataclass(frozen=True)
class BasketRecord:
    cycle_id: str
    account_id: str
    gross: float
    commission: float
    swap: float
    fees: float
    net: float
    total_volume: float
    position_count: int
    duration_s: float
    confidence: str


def basket_from_cycle(cycle: Cycle) -> BasketRecord:
    m = cycle.members
    comm = sum(x["commission"] for x in m)
    swap = sum(x["swap"] for x in m)
    gross = sum(x["profit"] for x in m)
    return BasketRecord(
        cycle_id=cycle.cycle_id, account_id=cycle.account_id,
        gross=round(gross, 2), commission=round(comm, 2), swap=round(swap, 2),
        fees=0.0, net=round(gross + comm + swap, 2),
        total_volume=round(sum(x["volume"] for x in m), 2),
        position_count=len(m), duration_s=cycle.basket_close["duration_s"],
        confidence=cycle.confidence)


@dataclass(frozen=True)
class HypothesisResult:
    name: str
    description: str
    testable: bool
    n: int
    violations: int                 # realized below the trigger
    violation_pct: float
    overshoot_mean: float
    overshoot_p95: float
    mae: float


def _eval_threshold_hypothesis(name: str, description: str,
                               records: Sequence[BasketRecord],
                               threshold_of: Callable[[BasketRecord], float]) -> HypothesisResult:
    """A basket that closed realized `value`; the model would fire when the
    watched quantity >= threshold -> realized < threshold is a violation."""
    pairs = [(threshold_of(b), b.gross) for b in records]
    firings = [(t, g) for t, g in pairs if g >= t]
    violations = [(t, g) for t, g in pairs if g < t]
    overshoots = [g - t for t, g in firings]
    errors = [abs(g - t) for t, g in pairs]
    n = len(pairs)
    return HypothesisResult(
        name=name, description=description, testable=True, n=n,
        violations=len(violations),
        violation_pct=round(len(violations) / n * 100, 2) if n else 0.0,
        overshoot_mean=round(statistics.mean(overshoots), 3) if overshoots else 0.0,
        overshoot_p95=round(sorted(overshoots)[int(len(overshoots) * 0.95)], 3)
        if overshoots else 0.0,
        mae=round(statistics.mean(errors), 3) if errors else 0.0)


def replay_trigger_hypotheses(records: Sequence[BasketRecord]) -> List[HypothesisResult]:
    results = [
        _eval_threshold_hypothesis(
            "H_GROSS_1_00", "close when gross >= $1.00", records,
            lambda b: 1.00),
        _eval_threshold_hypothesis(
            "H_GROSS_1_10", "close when gross >= $1.10", records,
            lambda b: 1.10),
        _eval_threshold_hypothesis(
            "H_GROSS_1_68", "close when gross >= $1.68 (doc candidate)", records,
            lambda b: 1.68),
        _eval_threshold_hypothesis(
            "H_NET_1_00", "close when net >= $1.00", records,
            lambda b: 1.00 - b.commission - b.swap - b.fees),
        _eval_threshold_hypothesis(
            "H_PER_LOT_0_50", "gross >= lots*0.50", records,
            lambda b: b.total_volume * 0.50),
        _eval_threshold_hypothesis(
            "H_PER_LOT_0_85", "gross >= lots*0.85", records,
            lambda b: b.total_volume * 0.85),
        _eval_threshold_hypothesis(
            "H_PER_LOT_1_68", "gross >= lots*1.68", records,
            lambda b: b.total_volume * 1.68),
    ]
    return results


def summarize_baskets(records: Sequence[BasketRecord]) -> dict:
    gross = sorted(b.gross for b in records)
    n = len(gross)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "gross_min": gross[0],
        "gross_p5": gross[int(n * 0.05)],
        "gross_p25": gross[int(n * 0.25)],
        "gross_median": round(statistics.median(gross), 3),
        "gross_p75": gross[int(n * 0.75)],
        "gross_max": gross[-1],
        "losers": sum(1 for g in gross if g < -0.005),
        "winners_min": min((g for g in gross if g > 0.005), default=0.0),
    }


def trigger_conclusion(results: Sequence[HypothesisResult]) -> dict:
    """Honest conclusion: which hypotheses remain compatible with data."""
    compatible = [r for r in results if r.testable and r.violation_pct <= 5.0]
    return {
        "basket_amount": "OBSERVED",
        "compatible_hypotheses": [r.name for r in compatible],
        "trigger_status": ("PARTIAL" if 1 < len(compatible) else
                           ("UNKNOWN" if not compatible else
                            "PARTIAL")),  # even a single survivor cannot be
                                          # VERIFIED from close data alone
        "note": "Close-side data bounds the trigger from below but cannot "
                "observe the evaluation instant; tick-level data or a "
                "controlled test is required to elevate beyond PARTIAL.",
    }
