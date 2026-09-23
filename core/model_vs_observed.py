"""Model vs Observed comparison (Modules 10 & 14).

Compares observed MT5 behavior records against the SIMULATION MODEL and
produces MATCH / MISMATCH / UNKNOWN per check:

  - grid spacing        : |price difference| between consecutive grid adds
  - lot progression     : observed lot at level i vs model formula
  - grid level sequence : level numbering per side
  - basket close        : basket P/L at close events vs BasketCloseAllUSD
  - partial close       : presence/absence vs config flags
  - position count      : max observed open positions vs modeled depth
  - total lots          : observed total volume vs model

The simulation model is NEVER auto-adjusted from observations. The caller
may offer "Apply Observed Rule" which goes through
ModelVersionStore.apply_new_version() only after explicit user confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.mt5_adapters import (
    BehaviorRecord, EVENT_ADD_GRID, EVENT_OPEN_POSITION, EVENT_BASKET_CLOSE,
    EVENT_PARTIAL_CLOSE, EVENT_EMERGENCY, EVENT_FRIDAY_STOP, EVENT_DAILY_TARGET,
    EVENT_NEW_CYCLE,
)
from core.symbol_profile import SymbolProfile

MATCH = "MATCH"
MISMATCH = "MISMATCH"
UNKNOWN = "UNKNOWN"


@dataclass
class CheckResult:
    check: str
    result: str                 # MATCH / MISMATCH / UNKNOWN
    detail: str
    observed: str = ""
    model: str = ""
    samples: int = 0

    def to_dict(self) -> dict:
        return {
            "check": self.check, "result": self.result, "detail": self.detail,
            "observed": self.observed, "model": self.model, "samples": self.samples,
        }


@dataclass
class ComparisonReport:
    checks: List[CheckResult] = field(default_factory=list)
    match_count: int = 0
    mismatch_count: int = 0
    unknown_count: int = 0

    @property
    def overall(self) -> str:
        if self.mismatch_count > 0:
            return MISMATCH
        if self.match_count == 0 and self.unknown_count == 0:
            return UNKNOWN
        if self.match_count == 0:
            return UNKNOWN
        return MATCH

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "match_count": self.match_count,
            "mismatch_count": self.mismatch_count,
            "unknown_count": self.unknown_count,
            "checks": [ch.to_dict() for ch in self.checks],
        }


def _side_events(records: List[BehaviorRecord], side: str) -> List[BehaviorRecord]:
    """Entry events for one side. NEW_CYCLE counts as the first entry when the
    user logged price/lot on it (common in manual behavior records)."""
    return [r for r in records
            if r.side == side
            and r.event in (EVENT_OPEN_POSITION, EVENT_ADD_GRID, EVENT_NEW_CYCLE)
            and r.price is not None]


def check_grid_spacing(records: List[BehaviorRecord], config: EAConfig,
                       tolerance_pct: float = 10.0) -> CheckResult:
    """Observed spacing = |price difference| between consecutive entries per side."""
    samples: List[float] = []
    for side in ("BUY", "SELL"):
        evs = _side_events(records, side)
        for a, b in zip(evs, evs[1:]):
            samples.append(abs(b.price - a.price))
    if len(samples) < 2:
        return CheckResult("Grid spacing", UNKNOWN,
                           "need >= 3 priced entry events per side to measure spacing",
                           samples=len(samples))
    avg = sum(samples) / len(samples)
    tol = config.GridStepUSD * tolerance_pct / 100.0
    diffs = [abs(s - config.GridStepUSD) for s in samples]
    within = sum(1 for d in diffs if d <= tol)
    ratio = within / len(samples)
    if ratio >= 0.8:
        res, detail = MATCH, (f"{within}/{len(samples)} spacings within "
                              f"{tolerance_pct}% of GridStepUSD={config.GridStepUSD} "
                              f"(avg observed {avg:.2f})")
    else:
        res, detail = MISMATCH, (f"only {within}/{len(samples)} spacings within "
                                 f"{tolerance_pct}% of GridStepUSD={config.GridStepUSD} "
                                 f"(avg observed {avg:.2f})")
    return CheckResult("Grid spacing", res, detail,
                       observed=f"avg {avg:.2f}", model=f"{config.GridStepUSD}",
                       samples=len(samples))


def check_lot_progression(records: List[BehaviorRecord], config: EAConfig,
                          rules: SimulationModelRules, profile: SymbolProfile,
                          tolerance_lots: Optional[float] = None) -> CheckResult:
    tol = tolerance_lots if tolerance_lots is not None else profile.lot_step
    samples = 0
    within = 0
    worst: Optional[Tuple[int, float, float]] = None
    for side in ("BUY", "SELL"):
        evs = _side_events(records, side)
        level = 0
        for r in evs:
            level += 1
            if r.lot is None:
                continue
            model_lot = c.lot_for_level(config, level, rules, profile).value
            samples += 1
            if abs(r.lot - model_lot) <= tol + 1e-9:
                within += 1
            elif worst is None:
                worst = (level, r.lot, model_lot)
    if samples == 0:
        return CheckResult("Lot progression", UNKNOWN,
                           "no entry events with a lot value")
    if within == samples:
        return CheckResult("Lot progression", MATCH,
                           f"all {samples} observed lots within {tol} of model",
                           samples=samples)
    ratio = within / samples
    res = MATCH if ratio >= 0.8 else MISMATCH
    detail = (f"{within}/{samples} observed lots within tolerance {tol}")
    if worst:
        detail += f"; e.g. level {worst[0]}: observed {worst[1]} vs model {worst[2]}"
    return CheckResult("Lot progression", res, detail, samples=samples)


def check_grid_levels(records: List[BehaviorRecord]) -> CheckResult:
    """Level numbering: model expects strictly increasing 1,2,3... per side."""
    ok, total = 0, 0
    for side in ("BUY", "SELL"):
        expected = 0
        for r in _side_events(records, side):
            expected += 1
            if r.grid_level is None:
                continue
            total += 1
            if r.grid_level == expected:
                ok += 1
    if total == 0:
        return CheckResult("Grid level sequence", UNKNOWN,
                           "no events carry an explicit grid_level")
    res = MATCH if ok == total else MISMATCH
    return CheckResult("Grid level sequence", res,
                       f"{ok}/{total} events match sequential numbering", samples=total)


def check_basket_close(records: List[BehaviorRecord], config: EAConfig,
                       tolerance_usd: float = 0.5) -> CheckResult:
    closes = [r for r in records if r.event == EVENT_BASKET_CLOSE]
    if not closes:
        if config.UseBasketCloseAll:
            return CheckResult("Basket close", UNKNOWN,
                               "no BASKET_CLOSE events observed yet")
        return CheckResult("Basket close", MATCH,
                           "basket close disabled in config and none observed")
    pls = [r.basket_pl if r.basket_pl is not None else r.floating_pl for r in closes]
    pls = [p for p in pls if p is not None]
    if not pls:
        return CheckResult("Basket close", UNKNOWN,
                           f"{len(closes)} close events but no basket P/L recorded")
    if not config.UseBasketCloseAll:
        return CheckResult("Basket close", MISMATCH,
                           f"{len(closes)} basket closes observed but UseBasketCloseAll=false")
    within = sum(1 for p in pls if abs(p - config.BasketCloseAllUSD) <= tolerance_usd)
    ratio = within / len(pls)
    res = MATCH if ratio >= 0.8 else MISMATCH
    avg = sum(pls) / len(pls)
    return CheckResult("Basket close", res,
                       f"{within}/{len(pls)} close P/L within {tolerance_usd} USD of "
                       f"target {config.BasketCloseAllUSD} (avg {avg:.2f})",
                       observed=f"avg {avg:.2f}", model=f"{config.BasketCloseAllUSD}",
                       samples=len(pls))


def check_partial_close(records: List[BehaviorRecord], config: EAConfig) -> CheckResult:
    partials = [r for r in records if r.event == EVENT_PARTIAL_CLOSE]
    if config.UseProfitPartialClose:
        if not partials:
            return CheckResult("Partial close", UNKNOWN,
                               "partial close enabled but no PARTIAL_CLOSE events observed "
                               "(may simply not have triggered)")
        return CheckResult("Partial close", MATCH,
                           f"{len(partials)} PARTIAL_CLOSE events observed while enabled",
                           samples=len(partials))
    if partials:
        return CheckResult("Partial close", MISMATCH,
                           f"{len(partials)} PARTIAL_CLOSE events observed while disabled",
                           samples=len(partials))
    return CheckResult("Partial close", MATCH,
                       "partial close disabled and none observed")


def check_position_count_and_lots(records: List[BehaviorRecord], config: EAConfig,
                                  rules: SimulationModelRules,
                                  profile: SymbolProfile,
                                  max_depth: int = 50) -> CheckResult:
    """Max observed simultaneous positions vs model lot totals at same depth."""
    count = 0
    max_count = 0
    max_lots = 0.0
    for r in records:
        if r.event in (EVENT_OPEN_POSITION, EVENT_ADD_GRID):
            count += 1
            max_count = max(max_count, count)
        elif r.event in (EVENT_BASKET_CLOSE, EVENT_PARTIAL_CLOSE):
            if r.position_count is not None:
                count = r.position_count
            elif count > 0 and r.event == EVENT_BASKET_CLOSE:
                count = 0
        if r.total_lots is not None:
            max_lots = max(max_lots, r.total_lots)
    if max_count == 0:
        return CheckResult("Position count / total lots", UNKNOWN,
                           "no entry events to count positions")
    model_lots, _ = c.lots_for_levels(config, min(max_count, max_depth), rules, profile)
    model_total = sum(model_lots)
    lots_detail = ""
    lots_res = UNKNOWN
    if max_lots > 0 and model_total > 0:
        diff_pct = abs(max_lots - model_total) / model_total * 100.0
        lots_res = MATCH if diff_pct <= 10.0 else MISMATCH
        lots_detail = (f"observed max total lots {max_lots} vs model {model_total:.2f} "
                       f"at depth {min(max_count, max_depth)} ({diff_pct:.1f}% off)")
    return CheckResult("Position count / total lots", lots_res,
                       f"max observed open positions: {max_count}. {lots_detail}",
                       observed=f"{max_count} pos / {max_lots} lots",
                       model=f"{model_total:.2f} lots", samples=max_count)


def compare_behavior(records: List[BehaviorRecord], config: EAConfig,
                     profile: SymbolProfile, rules: SimulationModelRules) -> ComparisonReport:
    report = ComparisonReport()
    report.checks = [
        check_grid_spacing(records, config),
        check_lot_progression(records, config, rules, profile),
        check_grid_levels(records),
        check_basket_close(records, config),
        check_partial_close(records, config),
        check_position_count_and_lots(records, config, rules, profile),
    ]
    report.match_count = sum(1 for ch in report.checks if ch.result == MATCH)
    report.mismatch_count = sum(1 for ch in report.checks if ch.result == MISMATCH)
    report.unknown_count = sum(1 for ch in report.checks if ch.result == UNKNOWN)
    return report


# ---------------------------------------------------------------------------
# Apply Observed Rule helpers (called ONLY after user confirmation)
# ---------------------------------------------------------------------------
def suggest_lot_rule_from_observed(records: List[BehaviorRecord],
                                   profile: SymbolProfile) -> Optional[dict]:
    """Fit candidate lot rules to observed (level, lot) data.

    GEOMETRIC  : lot = base * m^(level-1), m from log-linear least squares
    ARITHMETIC : lot = base + step*(level-1), step from endpoints
    FLAT       : lot = base

    Candidates are compared by mean absolute error with a simplest-first
    tie-break (FLAT < ARITHMETIC < GEOMETRIC), so a rule only wins when it
    fits strictly better. Returns None when there is not enough data.
    This NEVER changes the model - the UI presents it and the user decides.
    """
    import math
    from core.model_rules import LOT_GEOMETRIC, LOT_ARITHMETIC_STEP, LOT_FLAT
    pts: List[Tuple[int, float]] = []
    for side in ("BUY", "SELL"):
        level = 0
        for r in _side_events(records, side):
            level += 1
            if r.lot is not None:
                pts.append((level, r.lot))
    if len(pts) < 3:
        return None
    levels = [l for l, _ in pts]
    lots = [v for _, v in pts]
    base = lots[0]

    # geometric fit: least squares on ln(lot/base) = (level-1) * ln(m)
    num = den = 0.0
    for l, v in pts:
        if l > 1 and v > 0 and base > 0:
            num += (l - 1) * math.log(v / base)
            den += (l - 1) ** 2
    m = math.exp(num / den) if den > 0 else 1.0
    geo_pred = [base * (m ** (l - 1)) for l in levels]

    # arithmetic fit: lot = base + step*(l-1)
    step = (lots[-1] - lots[0]) / (levels[-1] - levels[0]) if levels[-1] != levels[0] else 0.0
    ar_pred = [base + step * (l - 1) for l in levels]

    flat_pred = [base] * len(levels)

    def mae(pred):
        return sum(abs(p - o) for p, o in zip(pred, lots)) / len(lots)

    candidates = {
        LOT_FLAT: {"mae": mae(flat_pred)},
        LOT_ARITHMETIC_STEP: {"mae": mae(ar_pred), "step_lots": round(step, 4)},
        LOT_GEOMETRIC: {"mae": mae(geo_pred), "multiplier": round(m, 4)},
    }
    # simplest-first tie-break: a rule must be strictly better to replace
    best_rule, best_params = None, None
    for rule, params in candidates.items():
        if best_params is None or params["mae"] < best_params["mae"]:
            best_rule, best_params = rule, params
    return {
        "points": len(pts),
        "best_rule": best_rule,
        "best_params": best_params,
        "candidates": candidates,
        "observed_points": pts[:20],
    }
