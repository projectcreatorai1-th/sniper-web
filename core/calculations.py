"""ALL simulation formulas live in this module (single source of truth).

No other module (core, GUI, adapters) may re-implement a formula;
they must call the functions here. GUI code only formats results.

Every function returns either a plain value or a structured result that
includes the assumption IDs it depends on, so the UI and reports can show
exactly which parts of a number rest on model assumptions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.assumptions import MODEL_ASSUMPTION
from core.config import EAConfig
from core.model_rules import (
    SimulationModelRules,
    LOT_GEOMETRIC, LOT_ARITHMETIC_STEP, LOT_FLAT,
)
from core.symbol_profile import SymbolProfile, AccountSettings

BUY = "BUY"
SELL = "SELL"


# ===========================================================================
# Structured result container
# ===========================================================================
@dataclass
class CalcResult:
    value: float
    assumptions: List[str] = field(default_factory=list)

    def rounded(self, nd: int = 2) -> float:
        return round(self.value, nd)


# ===========================================================================
# Lot sizing
# ===========================================================================
def normalize_lot(raw_lot: float, profile: SymbolProfile) -> float:
    """Normalize a raw lot to the broker's lot step by FLOORING.

    VERIFIED V1.68 BEHAVIOR (owner confirmation 2026-09-24, MC-001):
    floor(BaseLot x LotMultiplier^(n-1) / lot_step) x lot_step — observed
    on 4 real accounts, 4451/4451 checks on HIGH-confidence cycles
    (E012, E028). The earlier round-to-nearest model was INVALID: it
    disagrees at L5 (0.15 vs 0.14), L7, L10, L12, L14+ (82.90% match).
    Out-of-bound values are still surfaced by validation instead of
    silent min/max clamping (LOT_STEP_BOUNDARY_ASSUMPTION_001).
    """
    if profile.lot_step <= 0:
        return round(raw_lot, 8)
    steps = math.floor(raw_lot / profile.lot_step + 1e-9)
    return round(steps * profile.lot_step, 8)


def raw_lot_for_level(config: EAConfig, level: int, rules: SimulationModelRules) -> float:
    """Raw (unnormalized) lot for a grid level (1-based).

    Single source of truth for the lot progression formula.
    If UsePositionSizeOptimization=false every level uses BaseLot (documented
    as "ปิดระบบปรับขนาดล็อต" - the increase system is off).
    """
    if level < 1:
        raise ValueError("level must be >= 1")
    if not config.UsePositionSizeOptimization:
        return float(config.BaseLot)
    if rules.lot_formula == LOT_GEOMETRIC:
        # LOT_FORMULA_ASSUMPTION_001: BaseLot x LotMultiplier^(level-1)
        return float(config.BaseLot) * (float(config.LotMultiplier) ** (level - 1))
    if rules.lot_formula == LOT_ARITHMETIC_STEP:
        return float(config.BaseLot) + (level - 1) * float(rules.arithmetic_step_lots)
    if rules.lot_formula == LOT_FLAT:
        return float(config.BaseLot)
    raise ValueError(f"Unknown lot formula: {rules.lot_formula}")


def lot_for_level(config: EAConfig, level: int, rules: SimulationModelRules,
                  profile: SymbolProfile) -> CalcResult:
    raw = raw_lot_for_level(config, level, rules)
    normalized = normalize_lot(raw, profile)
    assumptions = ["LOT_FORMULA_ASSUMPTION_001", "LOT_NORMALIZATION_ASSUMPTION_001"]
    if not config.UsePositionSizeOptimization:
        assumptions = ["LOT_NORMALIZATION_ASSUMPTION_001"]
    return CalcResult(normalized, assumptions)


def lots_for_levels(config: EAConfig, levels: int, rules: SimulationModelRules,
                    profile: SymbolProfile) -> Tuple[List[float], List[str]]:
    lots = [lot_for_level(config, i, rules, profile).value for i in range(1, levels + 1)]
    return lots, ["LOT_FORMULA_ASSUMPTION_001", "LOT_NORMALIZATION_ASSUMPTION_001"]


def cumulative_lots(lots: List[float]) -> List[float]:
    out, total = [], 0.0
    for lot in lots:
        total = round(total + lot, 8)
        out.append(total)
    return out


# ===========================================================================
# Grid geometry
# ===========================================================================
def entry_price_for_level(start_price: float, level: int, side: str,
                          grid_step: float) -> float:
    """Entry price of a grid level.

    Model (GRID_TRIGGER_ASSUMPTION_001 + GRID_DIRECTION_ASSUMPTION_001):
    buy grid adds DOWN (adverse), sell grid adds UP.
    level 1 opens at start_price.
    """
    if level < 1:
        raise ValueError("level must be >= 1")
    offset = (level - 1) * grid_step
    if side == BUY:
        return start_price - offset
    if side == SELL:
        return start_price + offset
    raise ValueError(f"side must be {BUY} or {SELL}")


def levels_for_adverse_move(adverse_move: float, grid_step: float) -> int:
    """How many grid levels exist after an adverse price move of `adverse_move`.

    Level 1 at move=0; one extra level per full grid_step of adverse move.
    """
    if adverse_move < 0:
        raise ValueError("adverse_move must be >= 0")
    if grid_step <= 0:
        raise ValueError("grid_step must be > 0")
    return int(math.floor(adverse_move / grid_step)) + 1


# ===========================================================================
# P/L, exposure, margin
# ===========================================================================
def position_pl(side: str, entry_price: float, current_price: float,
                lots: float, profile: SymbolProfile) -> float:
    """P/L in account currency for a single position.

    PL_CONVERSION_ASSUMPTION_001: price_diff x lots x contract_size,
    no spread/commission/swap.
    """
    diff = (current_price - entry_price) if side == BUY else (entry_price - current_price)
    return diff * lots * profile.contract_size


def basket_pl(positions: List[Tuple[str, float, float]], current_price: float,
              profile: SymbolProfile) -> float:
    """Sum of position P/L. positions = [(side, entry_price, lots), ...]."""
    return round(sum(position_pl(s, e, current_price, l, profile)
                     for s, e, l in positions), 8)


def notional_exposure(lots: float, price: float, profile: SymbolProfile) -> float:
    """Notional exposure (EXPOSURE_ASSUMPTION_001)."""
    return lots * profile.contract_size * price


def margin_used(lots: float, price: float, profile: SymbolProfile,
                account: AccountSettings) -> float:
    """Margin estimate (MARGIN_ASSUMPTION_001):
    lots x contract_size x price / leverage x margin_rate."""
    if account.leverage <= 0:
        raise ValueError("leverage must be > 0")
    return lots * profile.contract_size * price / account.leverage * account.margin_rate


def drawdown_percent(floating_pl: float, capital: float) -> float:
    """Drawdown % of capital from a (negative) floating P/L."""
    if capital <= 0:
        raise ValueError("capital must be > 0")
    return round(abs(min(floating_pl, 0.0)) / capital * 100.0, 4)


def margin_level_percent(equity: float, margin: float) -> Optional[float]:
    """Margin level = equity / margin x 100. None when margin==0."""
    if margin <= 0:
        return None
    return equity / margin * 100.0


# ===========================================================================
# Basket math (targets / partial close)
# ===========================================================================
def price_move_for_basket_target(current_pl: float, total_lots: float,
                                 target_pl: float, profile: SymbolProfile) -> Optional[float]:
    """Additional favorable price move needed for the basket to reach target.

    P/L sensitivity to price = total_lots x contract_size.
    Returns None when total_lots == 0.
    """
    sensitivity = total_lots * profile.contract_size
    if sensitivity <= 0:
        return None
    return round((target_pl - current_pl) / sensitivity, 8)


def weighted_average_entry(positions: List[Tuple[str, float, float]]) -> Optional[float]:
    """Volume-weighted average entry of a one-side position list."""
    total_lots = sum(l for _, _, l in positions)
    if total_lots <= 0:
        return None
    return sum(e * l for _, e, l in positions) / total_lots


def partial_close_volume(total_lots: float, percent: float,
                         profile: SymbolProfile) -> float:
    """Volume closed by a partial close (PARTIAL_CLOSE_ASSUMPTION_001:
    percent of total volume, pro-rata across orders, normalized to lot step)."""
    closed = total_lots * (percent / 100.0)
    return normalize_lot(closed, profile)


def partial_close_realized_pl(basket_pl_at_trigger: float, percent: float,
                              rule: str) -> float:
    """Realized P/L of a partial close.

    PRO_RATA model: realizes `percent`% of basket P/L. If the EX5 instead
    closes specific (profitable) orders first, realized amount would differ -
    PARTIAL_CLOSE_ASSUMPTION_001 stays attached.
    """
    return round(basket_pl_at_trigger * (percent / 100.0), 8)


# ===========================================================================
# Basket composition helper
# ===========================================================================
def build_side_positions(config: EAConfig, side: str, start_price: float,
                         levels: int, rules: SimulationModelRules,
                         profile: SymbolProfile) -> Tuple[List[Tuple[str, float, float]], List[str]]:
    """Positions [(side, entry, lots)] for one grid side at `levels` depth."""
    side_enabled = config.UseGridBuy if side == BUY else config.UseGridSell
    if not side_enabled or levels <= 0:
        return [], []
    lots, assumptions = lots_for_levels(config, levels, rules, profile)
    positions = [(side, entry_price_for_level(start_price, i, side, config.GridStepUSD), lots[i - 1])
                 for i in range(1, levels + 1)]
    return positions, assumptions + [
        "GRID_TRIGGER_ASSUMPTION_001", "GRID_DIRECTION_ASSUMPTION_001",
    ]


# Assumption bundles reused by result objects
GRID_TABLE_ASSUMPTIONS = [
    "LOT_FORMULA_ASSUMPTION_001",
    "LOT_NORMALIZATION_ASSUMPTION_001",
    "GRID_TRIGGER_ASSUMPTION_001",
    "GRID_DIRECTION_ASSUMPTION_001",
    "PL_CONVERSION_ASSUMPTION_001",
    "MARGIN_ASSUMPTION_001",
    "EXPOSURE_ASSUMPTION_001",
]
WORST_CASE_ASSUMPTIONS = GRID_TABLE_ASSUMPTIONS + [
    "BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001",
]
BASKET_ASSUMPTIONS = [
    "BASKET_CLOSE_DOC_001",
    "BASKET_SCOPE_ASSUMPTION_001",
    "PARTIAL_CLOSE_ASSUMPTION_001",
    "PL_CONVERSION_ASSUMPTION_001",
]
