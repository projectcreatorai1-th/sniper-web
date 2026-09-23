"""Risk Dashboard (Module 5).

Aggregates grid + worst-case numbers into a summary with risk flags.
Flags fire against USER-CONFIGURABLE thresholds - there are deliberately no
"best/worst" scores, only measured data and warnings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core import calculations as c
from core.config import EAConfig
from core.grid import GridTable, build_grid_table
from core.model_rules import SimulationModelRules
from core.symbol_profile import SymbolProfile, AccountSettings
from core.worst_case import WorstCaseResult, simulate_worst_case, BOTH_SIDES

FLAG_HIGH_LOT_GROWTH = "HIGH LOT GROWTH"
FLAG_HIGH_GRID_DEPTH = "HIGH GRID DEPTH"
FLAG_HIGH_ESTIMATED_DD = "HIGH ESTIMATED DD"
FLAG_LOW_CAPITAL_BUFFER = "LOW CAPITAL BUFFER"
FLAG_HIGH_MARGIN_USAGE = "HIGH MARGIN USAGE"
FLAG_MODEL_ASSUMPTION = "MODEL ASSUMPTION"
FLAG_EA_BEHAVIOR_NOT_VERIFIED = "EA BEHAVIOR NOT VERIFIED"
FLAG_EMERGENCY_DISABLED = "EMERGENCY STOP DISABLED"


@dataclass
class RiskThresholds:
    high_lot_growth_multiplier: float = 1.5
    high_grid_depth_levels: int = 20
    high_dd_percent: float = 30.0
    low_capital_buffer_percent: float = 20.0   # remaining equity <= 20% of capital
    high_margin_usage_percent: float = 50.0    # margin used > 50% of capital
    max_simulated_grid_levels: int = 30
    reference_adverse_move_usd: float = 50.0

    def to_dict(self) -> dict:
        return {
            "high_lot_growth_multiplier": self.high_lot_growth_multiplier,
            "high_grid_depth_levels": self.high_grid_depth_levels,
            "high_dd_percent": self.high_dd_percent,
            "low_capital_buffer_percent": self.low_capital_buffer_percent,
            "high_margin_usage_percent": self.high_margin_usage_percent,
            "max_simulated_grid_levels": self.max_simulated_grid_levels,
            "reference_adverse_move_usd": self.reference_adverse_move_usd,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RiskThresholds":
        t = cls()
        for k, v in (d or {}).items():
            if hasattr(t, k) and v is not None:
                setattr(t, k, v)
        return t


@dataclass
class RiskFlag:
    flag: str
    detail: str
    severity: str          # "warning" | "info"

    def to_dict(self) -> dict:
        return {"flag": self.flag, "detail": self.detail, "severity": self.severity}


@dataclass
class RiskSummary:
    capital: float
    base_lot: float
    grid_step: float
    lot_multiplier: float
    max_simulated_grid: int
    total_lots: float
    estimated_exposure: float
    estimated_worst_floating_loss: float
    estimated_dd_percent: float
    margin_used: float
    margin_usage_percent: float
    remaining_equity: float
    basket_target: Optional[float]
    flags: List[RiskFlag] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "capital": self.capital,
            "base_lot": self.base_lot,
            "grid_step": self.grid_step,
            "lot_multiplier": self.lot_multiplier,
            "max_simulated_grid": self.max_simulated_grid,
            "total_lots": round(self.total_lots, 4),
            "estimated_exposure": round(self.estimated_exposure, 2),
            "estimated_worst_floating_loss": round(self.estimated_worst_floating_loss, 2),
            "estimated_dd_percent": round(self.estimated_dd_percent, 4),
            "margin_used": round(self.margin_used, 2),
            "margin_usage_percent": round(self.margin_usage_percent, 4),
            "remaining_equity": round(self.remaining_equity, 2),
            "basket_target": self.basket_target,
            "flags": [f.to_dict() for f in self.flags],
            "assumptions": self.assumptions,
        }


def build_risk_summary(config: EAConfig, profile: SymbolProfile,
                       account: AccountSettings, rules: SimulationModelRules,
                       capital: float, thresholds: RiskThresholds,
                       side: str = c.BUY) -> RiskSummary:
    if capital <= 0:
        raise ValueError("capital must be > 0")
    levels = max(1, int(thresholds.max_simulated_grid_levels))
    table: GridTable = build_grid_table(config, profile, account, rules, levels, side)
    worst: WorstCaseResult = simulate_worst_case(
        config, profile, account, rules, capital,
        thresholds.reference_adverse_move_usd, BOTH_SIDES)

    margin_usage_pct = worst.estimated_margin_used / capital * 100.0

    flags: List[RiskFlag] = []
    if config.UsePositionSizeOptimization and config.LotMultiplier >= thresholds.high_lot_growth_multiplier:
        flags.append(RiskFlag(
            FLAG_HIGH_LOT_GROWTH,
            f"LotMultiplier {config.LotMultiplier} >= threshold "
            f"{thresholds.high_lot_growth_multiplier}",
            "warning"))
    if levels >= thresholds.high_grid_depth_levels:
        flags.append(RiskFlag(
            FLAG_HIGH_GRID_DEPTH,
            f"Simulated grid depth {levels} >= threshold {thresholds.high_grid_depth_levels}",
            "warning"))
    if worst.drawdown_pct >= thresholds.high_dd_percent:
        flags.append(RiskFlag(
            FLAG_HIGH_ESTIMATED_DD,
            f"Estimated DD {worst.drawdown_pct:.1f}% at a {thresholds.reference_adverse_move_usd} "
            f"USD adverse move >= threshold {thresholds.high_dd_percent}%",
            "warning"))
    buffer_pct = worst.remaining_capital / capital * 100.0
    if buffer_pct <= thresholds.low_capital_buffer_percent:
        flags.append(RiskFlag(
            FLAG_LOW_CAPITAL_BUFFER,
            f"Remaining equity {worst.remaining_capital:.2f} "
            f"({buffer_pct:.1f}% of capital) <= threshold "
            f"{thresholds.low_capital_buffer_percent}%",
            "warning"))
    if margin_usage_pct > thresholds.high_margin_usage_percent:
        flags.append(RiskFlag(
            FLAG_HIGH_MARGIN_USAGE,
            f"Margin usage {margin_usage_pct:.1f}% > threshold "
            f"{thresholds.high_margin_usage_percent}%",
            "warning"))
    if not config.EnableEmergencyStop:
        flags.append(RiskFlag(
            FLAG_EMERGENCY_DISABLED,
            "EnableEmergencyStop=false - no emergency brake active",
            "info"))
    # honesty flags: always present
    flags.append(RiskFlag(
        FLAG_MODEL_ASSUMPTION,
        "Core numbers rest on simulation model assumptions "
        "(see Assumption Registry)",
        "warning"))
    flags.append(RiskFlag(
        FLAG_EA_BEHAVIOR_NOT_VERIFIED,
        "Internal EX5 behavior is not verified - this is a calculator/simulator, "
        "not a reproduction of the EA",
        "warning"))

    assumptions = list(dict.fromkeys(table.assumptions + worst.assumptions))

    return RiskSummary(
        capital=capital,
        base_lot=config.BaseLot,
        grid_step=config.GridStepUSD,
        lot_multiplier=config.LotMultiplier,
        max_simulated_grid=levels,
        total_lots=worst.total_lots,
        estimated_exposure=worst.estimated_exposure,
        estimated_worst_floating_loss=worst.floating_pl,
        estimated_dd_percent=worst.drawdown_pct,
        margin_used=worst.estimated_margin_used,
        margin_usage_percent=round(margin_usage_pct, 4),
        remaining_equity=worst.remaining_capital,
        basket_target=config.BasketCloseAllUSD if config.UseBasketCloseAll else None,
        flags=flags,
        assumptions=assumptions,
    )
