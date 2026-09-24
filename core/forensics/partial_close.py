"""Partial close engine — deal-level reconstruction and classification.

METHOD (correct, deal-level):
  Out-deals are matched to position rows by (close_time, opposite side,
  volume). Matched deals = full-position closes. UNMATCHED out-deals are
  intra-position partial closes — the Positions table only shows each
  position's final remaining volume, so partials are invisible there.

  Each partial is attributed to a position (same side, open during the
  event, remaining volume sufficient) preferring the oldest candidate
  (FIFO preference); attribution confidence is reported, not assumed.

Separate rule statuses (never merged):
  PARTIAL_EXISTS       partial closes happen (count, per account)
  PARTIAL_TRIGGER      what fires them (UNKNOWN — but profit-per-event
                       distribution is reported; median ~ +1.0)
  PARTIAL_VOLUME_RULE  how much volume closes per event
  PARTIAL_LEVEL_RULE   which position is targeted (attribution-based)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from core.forensics.cycle_reconstruction import FMT
from core.forensics.mt5_report import MT5Report


@dataclass(frozen=True)
class PartialDeal:
    account_id: str
    time: str
    deal_id: str
    order_id: str
    side: str                 # deal side (opposite of the position side)
    position_side: str
    volume: float
    price: float
    profit: float
    attributed_ticket: Optional[str]
    attribution: str          # FIFO_FEASIBLE / AMBIGUOUS / UNATTRIBUTED


def _opposite(side: str) -> str:
    return "SELL" if side == "BUY" else "BUY"


def extract_partial_deals(report: MT5Report) -> List[PartialDeal]:
    """Unmatched out-deals = intra-position partial closes."""
    row_index: dict = {}
    for p in report.positions:
        if p.close_time:
            key = (p.close_time, _opposite(p.side), round(p.volume, 2))
            row_index.setdefault(key, []).append(p)

    open_at = []   # (open_time, close_time_or_inf, side, ticket, volume)
    for p in report.positions:
        open_at.append((p.open_time, p.close_time or "9999.99.99 99:99:99",
                        p.side, p.ticket, p.volume))
    for p in report.open_positions:
        open_at.append((p["open_time"], "9999.99.99 99:99:99",
                        p["side"], p["ticket"], p["volume"]))
    open_at.sort()

    partials: List[PartialDeal] = []
    for d in sorted(report.out_deals, key=lambda x: x.time):
        key = (d.time, d.side, round(d.volume, 2))
        rows = row_index.get(key)
        if rows:
            rows.pop()          # matched: full close of that row
            if not rows:
                del row_index[key]
            continue
        # partial close: attribute to oldest feasible position on the
        # opposite side (deal side closes a position of the opposite side)
        pside = _opposite(d.side)
        attributed, how = None, "UNATTRIBUTED"
        feasible = [t for t in open_at
                    if t[2] == pside and t[0] <= d.time <= t[1]
                    and t[4] + 1e-9 >= d.volume]
        if feasible:
            oldest = min(feasible, key=lambda t: t[0])
            attributed, how = oldest[3], "FIFO_FEASIBLE"
            if len(feasible) > 1:
                how = "AMBIGUOUS" if any(
                    abs((_dt(feasible_i[0]) - _dt(oldest[0])).total_seconds()) < 60
                    for feasible_i in feasible if feasible_i[3] != oldest[3]) else "FIFO_FEASIBLE"
        partials.append(PartialDeal(
            account_id=report.account_id, time=d.time, deal_id=d.deal_id,
            order_id=d.order_id, side=d.side, position_side=pside,
            volume=d.volume, price=d.price, profit=d.profit,
            attributed_ticket=attributed, attribution=how))
    return partials


def _dt(ts: str) -> datetime:
    return datetime.strptime(ts, FMT)


def classify_partial_deals(partials: Sequence[PartialDeal],
                           reports: Sequence[MT5Report]) -> dict:
    n = len(partials)
    if not n:
        return {"PARTIAL_EXISTS": "UNKNOWN", "n_events": 0}
    profits = [p.profit for p in partials]
    vols = [p.volume for p in partials]
    near_target = sum(1 for x in profits if 0.7 <= x <= 1.3)
    per_lot = [p.profit / p.volume for p in partials if p.volume > 0]
    attributed = [p for p in partials if p.attributed_ticket]
    # which ladder level gets partial-closed: look up attributed positions
    levels = []
    for rep in reports:
        pos = {p.ticket: p for p in rep.positions}
        for p in attributed:
            if p.account_id != rep.account_id:
                continue
            row = pos.get(p.attributed_ticket)
            if row:
                from core.forensics.lot_engine import DEFAULT_ENGINE
                lvl = DEFAULT_ENGINE.level_of_lot(row.volume + p.volume)
                if lvl:
                    levels.append(lvl)
    return {
        "PARTIAL_EXISTS": "VERIFIED" if n >= 10 else "OBSERVED",
        "n_events": n,
        "per_account": {a: sum(1 for p in partials if p.account_id == a)
                        for a in sorted({p.account_id for p in partials})},
        "profit": {"median": round(statistics.median(profits), 3),
                   "mean": round(statistics.mean(profits), 3),
                   "min": round(min(profits), 2),
                   "max": round(max(profits), 2),
                   "in_0_7_1_3_pct": round(near_target / n * 100, 1)},
        "volume": {"median": round(statistics.median(vols), 2),
                   "min": min(vols), "max": max(vols)},
        "profit_per_lot_median": round(statistics.median(per_lot), 3),
        "attribution": {"attributed": len(attributed),
                        "fifo_feasible": sum(1 for p in partials
                                             if p.attribution == "FIFO_FEASIBLE"),
                        "ambiguous": sum(1 for p in partials
                                         if p.attribution == "AMBIGUOUS"),
                        "unattributed": sum(1 for p in partials
                                            if p.attribution == "UNATTRIBUTED")},
        "PARTIAL_TRIGGER": {
            "status": "UNKNOWN",
            "note": "profit-per-event median ~ +1.0 matches the basket "
                    "trigger scale, but the evaluation instant and watched "
                    "quantity (position / side / basket) are unobservable "
                    "from close-side data",
        },
        "PARTIAL_VOLUME_RULE": {
            "status": "UNKNOWN",
            "note": "partial volumes span 0.10-0.17; without the EA's "
                    "requested-vs-position arithmetic the fraction rule "
                    "cannot be derived",
        },
        "PARTIAL_LEVEL_RULE": {
            "status": "PARTIAL" if attributed else "UNKNOWN",
            "level_distribution_hint": (sorted(levels)[:200] if levels else []),
            "note": "FIFO-feasible attribution only; ambiguity reported, "
                    "not resolved",
        },
    }
