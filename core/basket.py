"""Basket / Partial Close simulation (Module 4).

Simulates basket-close and partial-close behavior for a grid basket at a
given depth, using the formulas from core.calculations only.

Everything here is SIMULATION - the internal EX5 logic is not verified
(see BASKET_* / PARTIAL_* assumptions).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.symbol_profile import SymbolProfile


@dataclass
class BasketSimResult:
    side: str
    levels: int
    total_lots: float
    avg_entry: Optional[float]
    current_price: float
    current_basket_pl: float
    partial_trigger: Optional[float]
    partial_pending: bool
    partial_close_volume: float
    partial_realized_pl: float
    partial_remaining_lots: float
    basket_target: Optional[float]
    price_move_to_partial: Optional[float]
    price_move_to_target: Optional[float]
    remaining_position_note: str
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "side": self.side,
            "levels": self.levels,
            "total_lots": self.total_lots,
            "avg_entry": self.avg_entry,
            "current_price": self.current_price,
            "current_basket_pl": round(self.current_basket_pl, 2),
            "partial_trigger": self.partial_trigger,
            "partial_pending": self.partial_pending,
            "partial_close_volume": self.partial_close_volume,
            "partial_realized_pl": round(self.partial_realized_pl, 2),
            "partial_remaining_lots": self.partial_remaining_lots,
            "basket_target": self.basket_target,
            "price_move_to_partial": self.price_move_to_partial,
            "price_move_to_target": self.price_move_to_target,
            "remaining_position_note": self.remaining_position_note,
            "assumptions": self.assumptions,
        }


def simulate_basket(config: EAConfig, profile: SymbolProfile,
                    rules: SimulationModelRules, side: str, levels: int,
                    start_price: Optional[float] = None,
                    current_price: Optional[float] = None,
                    partial_already_done: bool = False) -> BasketSimResult:
    """Evaluate basket state for one side at `levels` depth.

    current_price defaults to the entry price of the deepest level (the worst
    point of the adverse move), so basket P/L starts from the deepest drawdown.
    """
    if levels < 1:
        raise ValueError("levels must be >= 1")
    p0 = float(start_price if start_price is not None else profile.reference_price)
    positions, assumptions = c.build_side_positions(config, side, p0, levels, rules, profile)
    assumptions = list(dict.fromkeys(assumptions + c.BASKET_ASSUMPTIONS))

    lots = sum(l for _, _, l in positions)
    avg = c.weighted_average_entry(positions)
    deepest_entry = c.entry_price_for_level(p0, levels, side, config.GridStepUSD)
    cur = float(current_price if current_price is not None else deepest_entry)

    pl_now = c.basket_pl(positions, cur, profile)

    trigger = config.ProfitPartialTriggerUSD if config.UseProfitPartialClose else None
    target = config.BasketCloseAllUSD if config.UseBasketCloseAll else None

    move_to_partial = None
    move_to_target = None
    pending = False
    closed_vol = 0.0
    realized = 0.0
    remaining = lots

    if trigger is not None:
        pending = (not partial_already_done) or (not config.ProfitPartialOnlyOnce)
        move_to_partial = c.price_move_for_basket_target(pl_now, lots, trigger, profile)
        closed_vol = c.partial_close_volume(lots, config.ProfitPartialPercent, profile)
        realized = c.partial_close_realized_pl(trigger, config.ProfitPartialPercent,
                                               rules.partial_close_rule)
        remaining = round(lots - closed_vol, 8)
    if target is not None:
        move_to_target = c.price_move_for_basket_target(pl_now, lots, target, profile)

    note = (f"After partial close: {remaining} lots remain "
            f"(avg entry {round(avg, 6) if avg else 'n/a'} unchanged in pro-rata model)")

    return BasketSimResult(
        side=side,
        levels=levels,
        total_lots=round(lots, 4),
        avg_entry=avg,
        current_price=cur,
        current_basket_pl=pl_now,
        partial_trigger=trigger,
        partial_pending=pending,
        partial_close_volume=closed_vol,
        partial_realized_pl=realized,
        partial_remaining_lots=remaining,
        basket_target=target,
        price_move_to_partial=move_to_partial,
        price_move_to_target=move_to_target,
        remaining_position_note=note,
        assumptions=assumptions,
    )
