"""Worst Case Simulator (Module 3).

Simulates a one-directional market move against the grid and reports the
state at the end of the move. Three scenarios per move size:

  BUY_ADVERSE   - price falls; buy grid stacks levels and floats negative,
                  sell grid (if enabled) holds its level-1 hedge position
  SELL_ADVERSE  - mirror for a rising market
  BOTH_SIDES    - both grids active in the same adverse move (hedge offset)

All numbers are SIMULATION MODEL estimates - not verified EX5 behavior and
not a substitute for a real Strategy Tester run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.symbol_profile import SymbolProfile, AccountSettings

BUY_ADVERSE = "BUY_ADVERSE"
SELL_ADVERSE = "SELL_ADVERSE"
BOTH_SIDES = "BOTH_SIDES"
SCENARIOS = (BUY_ADVERSE, SELL_ADVERSE, BOTH_SIDES)


@dataclass
class WorstCaseResult:
    scenario: str
    adverse_move: float
    end_price: float
    grid_levels: int
    total_lots: float
    floating_pl: float                  # negative = floating loss
    estimated_exposure: float
    estimated_margin_used: float
    equity: float
    drawdown_pct: float
    margin_level_pct: Optional[float]
    remaining_capital: float
    emergency_triggered: bool
    emergency_note: str
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "adverse_move": self.adverse_move,
            "end_price": round(self.end_price, 6),
            "grid_levels": self.grid_levels,
            "total_lots": round(self.total_lots, 4),
            "floating_pl": round(self.floating_pl, 2),
            "estimated_exposure": round(self.estimated_exposure, 2),
            "estimated_margin_used": round(self.estimated_margin_used, 2),
            "equity": round(self.equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "margin_level_pct": round(self.margin_level_pct, 2) if self.margin_level_pct is not None else None,
            "remaining_capital": round(self.remaining_capital, 2),
            "emergency_triggered": self.emergency_triggered,
            "emergency_note": self.emergency_note,
            "assumptions": self.assumptions,
        }


def _side_state(config: EAConfig, profile: SymbolProfile, account: AccountSettings,
                rules: SimulationModelRules, side: str, p0: float, adverse_move: float):
    """Compute (positions, lots, margin, exposure) for one side after a move."""
    levels = c.levels_for_adverse_move(adverse_move, config.GridStepUSD)
    positions, _ = c.build_side_positions(config, side, p0, levels, rules, profile)
    lots = sum(l for _, _, l in positions)
    # margin/exposure evaluated at the entry prices actually paid
    margin = sum(c.margin_used(l, e, profile, account) for _, e, l in positions)
    exposure = sum(c.notional_exposure(l, e, profile) for _, e, l in positions)
    return positions, lots, margin, exposure, levels


def simulate_worst_case(config: EAConfig, profile: SymbolProfile,
                        account: AccountSettings, rules: SimulationModelRules,
                        capital: float, adverse_move: float, scenario: str,
                        start_price: Optional[float] = None) -> WorstCaseResult:
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    if capital <= 0:
        raise ValueError("capital must be > 0")
    if adverse_move < 0:
        raise ValueError("adverse_move must be >= 0")
    p0 = float(start_price if start_price is not None else profile.reference_price)

    assumptions = list(c.WORST_CASE_ASSUMPTIONS)

    if scenario == BUY_ADVERSE or scenario == BOTH_SIDES:
        # price falls by adverse_move
        end_price = p0 - adverse_move
        buy_positions, _, margin_b, exposure_b, levels_b = _side_state(
            config, profile, account, rules, c.BUY, p0, adverse_move)
        pl = c.basket_pl(buy_positions, end_price, profile)
        lots = sum(l for _, _, l in buy_positions)
        margin, exposure, levels = margin_b, exposure_b, levels_b
        if scenario == BOTH_SIDES and config.UseGridSell:
            # sell grid holds level-1 hedge (price never rose a full step)
            sell_positions, sell_lots, sell_margin, sell_exposure, _ = _side_state(
                config, profile, account, rules, c.SELL, p0, 0.0)
            pl += c.basket_pl(sell_positions, end_price, profile)
            lots += sell_lots
            margin += sell_margin
            exposure += sell_exposure
    else:  # SELL_ADVERSE
        end_price = p0 + adverse_move
        sell_positions, _, margin_s, exposure_s, levels_s = _side_state(
            config, profile, account, rules, c.SELL, p0, adverse_move)
        pl = c.basket_pl(sell_positions, end_price, profile)
        lots = sum(l for _, _, l in sell_positions)
        margin, exposure, levels = margin_s, exposure_s, levels_s

    equity = capital + pl
    dd_pct = c.drawdown_percent(pl, capital)
    mlvl = c.margin_level_percent(equity, margin)

    emergency_triggered = False
    emergency_note = "Emergency stop disabled (EnableEmergencyStop=false)"
    if config.EnableEmergencyStop and adverse_move > config.EmergencyDistanceFromCycleUSD:
        emergency_triggered = True
        emergency_note = (
            f"Emergency condition exceeded at ~{config.EmergencyDistanceFromCycleUSD} USD "
            f"(EMERGENCY_DOC_001 / EMERGENCY_FRAME_ASSUMPTION_001); "
            + ("EA would close all (EmergencyCloseAllWhenTriggered=true)"
               if config.EmergencyCloseAllWhenTriggered else
               "EA stops opening new orders (EmergencyCloseAllWhenTriggered=false)")
            + " - simulation still shows the full grid as a stress bound."
        )
        assumptions += ["EMERGENCY_DOC_001", "EMERGENCY_FRAME_ASSUMPTION_001"]

    return WorstCaseResult(
        scenario=scenario,
        adverse_move=adverse_move,
        end_price=end_price,
        grid_levels=levels,
        total_lots=round(lots, 4),
        floating_pl=round(pl, 2),
        estimated_exposure=round(exposure, 2),
        estimated_margin_used=round(margin, 2),
        equity=round(equity, 2),
        drawdown_pct=dd_pct,
        margin_level_pct=mlvl,
        remaining_capital=round(max(equity, 0.0), 2),
        emergency_triggered=emergency_triggered,
        emergency_note=emergency_note,
        assumptions=assumptions,
    )


DEFAULT_MOVE_PRESETS = (10.0, 20.0, 30.0, 50.0, 75.0, 100.0)


def simulate_moves(config: EAConfig, profile: SymbolProfile,
                   account: AccountSettings, rules: SimulationModelRules,
                   capital: float, moves: List[float],
                   start_price: Optional[float] = None) -> List[WorstCaseResult]:
    out = []
    for mv in moves:
        for scenario in (BUY_ADVERSE, SELL_ADVERSE, BOTH_SIDES):
            out.append(simulate_worst_case(config, profile, account, rules,
                                           capital, mv, scenario, start_price))
    return out
