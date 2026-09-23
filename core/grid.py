"""Grid Calculator (Module 2).

Builds the grid table for a chosen side and depth. All formulas come from
core.calculations (single source of truth); this module only orchestrates.

Every row carries the estimated floating P/L AT THE MOMENT that level opens
(current price = that level's entry price), margin estimate per level at
entry price, plus cumulative columns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.symbol_profile import SymbolProfile, AccountSettings


@dataclass
class GridRow:
    level: int
    entry_price: float
    distance_from_start: float
    lot: float
    cumulative_lot: float
    exposure: float
    margin: float
    floating_pl_at_open: float   # basket floating P/L when this level triggers
    avg_entry: Optional[float]


@dataclass
class GridTable:
    side: str
    start_price: float
    grid_step: float
    rows: List[GridRow] = field(default_factory=list)
    total_lot: float = 0.0
    total_exposure: float = 0.0
    total_margin: float = 0.0
    final_floating_pl: float = 0.0
    avg_entry: Optional[float] = None
    assumptions: List[str] = field(default_factory=list)

    def to_dicts(self) -> List[dict]:
        return [{
            "level": r.level,
            "entry_price": round(r.entry_price, 6),
            "distance_from_start": round(r.distance_from_start, 4),
            "lot": r.lot,
            "cumulative_lot": r.cumulative_lot,
            "exposure": round(r.exposure, 2),
            "margin": round(r.margin, 2),
            "floating_pl_at_open": round(r.floating_pl_at_open, 2),
            "avg_entry": round(r.avg_entry, 6) if r.avg_entry is not None else None,
        } for r in self.rows]


def build_grid_table(config: EAConfig, profile: SymbolProfile,
                     account: AccountSettings, rules: SimulationModelRules,
                     levels: int, side: str,
                     start_price: Optional[float] = None) -> GridTable:
    if levels < 1:
        raise ValueError("levels must be >= 1")
    p0 = float(start_price if start_price is not None else profile.reference_price)
    side_enabled = config.UseGridBuy if side == c.BUY else config.UseGridSell
    table = GridTable(side=side, start_price=p0, grid_step=config.GridStepUSD,
                      assumptions=list(c.GRID_TABLE_ASSUMPTIONS))
    if not side_enabled:
        return table

    lots, _ = c.lots_for_levels(config, levels, rules, profile)
    cum = c.cumulative_lots(lots)

    for i in range(1, levels + 1):
        entry = c.entry_price_for_level(p0, i, side, config.GridStepUSD)
        positions, _ = c.build_side_positions(config, side, p0, i, rules, profile)
        floating = c.basket_pl(positions, entry, profile)  # price at trigger = entry of level i
        avg = c.weighted_average_entry(positions)
        table.rows.append(GridRow(
            level=i,
            entry_price=entry,
            distance_from_start=round((i - 1) * config.GridStepUSD, 4),
            lot=lots[i - 1],
            cumulative_lot=cum[i - 1],
            exposure=c.notional_exposure(cum[i - 1], entry, profile),
            margin=c.margin_used(cum[i - 1], entry, profile, account),
            floating_pl_at_open=floating,
            avg_entry=avg,
        ))

    table.total_lot = cum[-1] if cum else 0.0
    table.total_exposure = c.notional_exposure(table.total_lot, p0, profile)
    table.total_margin = c.margin_used(table.total_lot, p0, profile, account)
    last_positions, _ = c.build_side_positions(config, side, p0, levels, rules, profile)
    table.final_floating_pl = c.basket_pl(last_positions, table.rows[-1].entry_price, profile)
    table.avg_entry = c.weighted_average_entry(last_positions)
    return table
