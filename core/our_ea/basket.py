"""Immutable cycle / basket identity (§16) + basket accounting (§21).

cycle_id / basket_id / sequence numbers are deterministic:
(account, symbol, sequence) — UI refresh, duplicate ticks and process
restarts can never mint a new identity for the same logical cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


def make_cycle_id(account: str, symbol: str, sequence: int) -> str:
    return f"{account}|{symbol}|C{sequence:06d}"


def make_basket_id(cycle_id: str) -> str:
    return f"{cycle_id}|B"


@dataclass(frozen=True)
class PositionRef:
    position_id: str
    side: str
    lot: float
    entry_price: float
    level: int
    opened_at: str = ""


class Basket:
    """Mutable working basket with IMMUTABLE identity (id never changes)."""

    def __init__(self, cycle_id: str, opened_at: str = ""):
        self.cycle_id = cycle_id
        self.basket_id = make_basket_id(cycle_id)
        self.opened_at = opened_at
        self.closed_at: Optional[str] = None
        self.positions: List[PositionRef] = []
        self.closed_positions: List[PositionRef] = []

    # -- identity ------------------------------------------------------
    @property
    def sequence_number(self) -> int:
        return int(self.cycle_id.rsplit("C", 1)[1])

    # -- accounting (§21) ----------------------------------------------
    def add(self, p: PositionRef) -> None:
        self.positions.append(p)

    def close_position(self, position_id: str, closed_at: str = "") -> PositionRef:
        for i, p in enumerate(self.positions):
            if p.position_id == position_id:
                self.positions.pop(i)
                self.closed_positions.append(p)
                if closed_at:
                    self.closed_at = closed_at
                return p
        raise KeyError(position_id)

    def total_lots(self, include_closed: bool = False) -> float:
        lots = sum(p.lot for p in self.positions)
        if include_closed:
            lots += sum(p.lot for p in self.closed_positions)
        return round(lots, 8)

    def levels(self, side: str) -> List[PositionRef]:
        return sorted([p for p in self.positions if p.side == side],
                      key=lambda p: p.level)

    def next_level(self, side: str) -> int:
        open_lv = [p.level for p in self.positions if p.side == side]
        closed_lv = [p.level for p in self.closed_positions if p.side == side]
        return max(open_lv + closed_lv + [0]) + 1

    def is_flat(self) -> bool:
        return not self.positions

    def summary(self) -> dict:
        return {"cycle_id": self.cycle_id, "basket_id": self.basket_id,
                "open_positions": len(self.positions),
                "closed_positions": len(self.closed_positions),
                "total_lots_open": self.total_lots(),
                "total_lots_all": self.total_lots(include_closed=True),
                "buy_levels": len(self.levels("BUY")),
                "sell_levels": len(self.levels("SELL")),
                "opened_at": self.opened_at, "closed_at": self.closed_at}


class BasketAccounting:
    """Profit accounting separated from decisions (§21)."""

    def __init__(self, contract_size: float = 1.0):
        self.contract_size = contract_size

    def position_pl(self, side: str, entry: float, price: float, lot: float) -> float:
        d = (price - entry) if side == "BUY" else (entry - price)
        return round(d * lot * self.contract_size, 8)

    def floating(self, basket: Basket, prices: Dict[str, float]) -> float:
        return round(sum(self.position_pl(p.side, p.entry_price,
                                          prices[p.side], p.lot)
                         for p in basket.positions), 8)

    def realized(self, closed_with_pl) -> float:
        return round(sum(closed_with_pl), 8)
