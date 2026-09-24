"""Cycle lifecycle model (Phase 1).

Cycle lifecycle is a MODEL - NOT VERIFIED INTERNAL EA BEHAVIOR:

  CYCLE_START_RULE_ASSUMPTION_001 (MODEL):
  Cycle begins when the simulation records its first position/open event.

  CYCLE_END_RULE_ASSUMPTION_001 (MODEL):
  Cycle ends when the configured terminal event closes the simulated cycle.

The builder aggregates OBSERVED records (BehaviorRecord) or MODEL positions
(from core.calculations - no new formulas). Missing data stays UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

from core.mt5_adapters import (
    BehaviorRecord,
    EVENT_ADD_GRID,
    EVENT_BASKET_CLOSE,
    EVENT_DAILY_TARGET,
    EVENT_EMERGENCY,
    EVENT_FRIDAY_STOP,
    EVENT_NEW_CYCLE,
    EVENT_OPEN_POSITION,
    EVENT_PARTIAL_CLOSE,
    EVENT_RESUME,
    EVENT_UNKNOWN,
)

SCHEMA = "SNIPER_CYCLE_V1"
TIMELINE_SCHEMA = "SNIPER_CYCLE_TIMELINE_V1"
TIMELINE_COMPLETE = "COMPLETE"
TIMELINE_INCOMPLETE = "INCOMPLETE"

# cycle statuses
OPEN = "OPEN"
CLOSED = "CLOSED"
EMERGENCY_CLOSED = "EMERGENCY_CLOSED"
UNKNOWN = "UNKNOWN"
CYCLE_STATUSES = (OPEN, CLOSED, EMERGENCY_CLOSED, UNKNOWN)

# events consumed by the cycle model (reuses the pipeline's event types)
CYCLE_EVENTS = (EVENT_NEW_CYCLE, EVENT_OPEN_POSITION, EVENT_ADD_GRID,
                EVENT_PARTIAL_CLOSE, EVENT_BASKET_CLOSE, EVENT_EMERGENCY,
                EVENT_FRIDAY_STOP, EVENT_DAILY_TARGET, EVENT_RESUME,
                EVENT_UNKNOWN)

START_EVENTS = (EVENT_NEW_CYCLE, EVENT_OPEN_POSITION)
TERMINAL_EVENTS = (EVENT_BASKET_CLOSE, EVENT_EMERGENCY, EVENT_FRIDAY_STOP,
                   EVENT_DAILY_TARGET)

CYCLE_START_RULE = ("MODEL: Cycle begins when the simulation records its first "
                    "position/open event. - MODEL, NOT VERIFIED INTERNAL EA BEHAVIOR")
CYCLE_END_RULE = ("MODEL: Cycle ends when the configured terminal event closes "
                  "the simulated cycle. - MODEL, NOT VERIFIED INTERNAL EA BEHAVIOR")


@dataclass
class Cycle:
    cycle_id: str = ""
    symbol: str = ""
    direction: str = UNKNOWN                    # BUY / SELL / mixed / UNKNOWN
    start_time: str = ""
    end_time: str = ""
    start_price: Optional[float] = None
    end_price: Optional[float] = None
    initial_lot: Optional[float] = None
    total_lots: Optional[float] = None
    grid_levels: int = 0
    basket_profit: Optional[float] = None
    realized_profit: Optional[float] = None
    floating_profit: Optional[float] = None
    status: str = UNKNOWN
    source: str = "observed"                    # observed | model
    close_reason: str = ""
    events: List[dict] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d


def build_cycles_from_records(records: List[BehaviorRecord]) -> List[Cycle]:
    """Segment observed behavior records into cycles using the MODEL rules.

    Pure accounting of the records' own fields - no EA formula is used or
    duplicated. Anything not present in the data stays None/UNKNOWN.

    NEW_CYCLE acts as a marker: it opens a pending cycle; the first
    OPEN_POSITION/ADD_GRID afterwards fills that same cycle (it does NOT
    start another one). A position event arriving while a cycle already
    holds positions, without a terminal event in between, supersedes the
    cycle - recorded as status UNKNOWN, never guessed.
    """
    cycles: List[Cycle] = []
    cur: Optional[Cycle] = None
    seq = 0
    realized = 0.0

    def close_active(reason_status: str, reason: str, rec: BehaviorRecord) -> None:
        nonlocal cur, realized
        if cur is None:
            return
        cur.end_time = rec.timestamp
        cur.end_price = rec.price if rec.price is not None else cur.end_price
        cur.status = reason_status
        cur.close_reason = reason
        cycles.append(cur)
        cur = None
        realized = 0.0

    def start_cycle(rec: BehaviorRecord, marker: bool) -> None:
        nonlocal cur, seq, realized
        seq += 1
        cur = Cycle(cycle_id=f"C{seq}", symbol=rec.symbol or UNKNOWN,
                    direction=rec.side or UNKNOWN,
                    start_time=rec.timestamp,
                    status=OPEN, events=[rec.to_dict()])
        realized = 0.0
        if not marker:
            _fill_first_position(cur, rec)

    def _fill_first_position(c: Cycle, rec: BehaviorRecord) -> None:
        c.start_price = rec.price
        c.initial_lot = rec.lot
        c.total_lots = rec.total_lots if rec.total_lots is not None else rec.lot
        c.grid_levels = 1

    for r in records:
        ev = r.event
        if ev == EVENT_NEW_CYCLE:
            if cur is not None and cur.grid_levels > 0:
                close_active(UNKNOWN, "superseded by NEW_CYCLE without terminal event", r)
            if cur is None:
                start_cycle(r, marker=True)
            else:
                cur.events.append(r.to_dict())
            continue
        if ev in (EVENT_OPEN_POSITION, EVENT_ADD_GRID):
            if cur is None:
                start_cycle(r, marker=False)
                continue
            if cur.grid_levels == 0:
                # first position of a cycle opened by a NEW_CYCLE marker
                if r.symbol and c_symbol_missing(cur):
                    cur.symbol = r.symbol
                if r.side and cur.direction == UNKNOWN:
                    cur.direction = r.side
                if not cur.start_time:
                    cur.start_time = r.timestamp
                cur.events.append(r.to_dict())
                _fill_first_position(cur, r)
                continue
            if ev == EVENT_OPEN_POSITION:
                # second OPEN inside a cycle without terminal -> superseded
                close_active(UNKNOWN, "superseded without terminal event", r)
                start_cycle(r, marker=False)
                continue
            cur.events.append(r.to_dict())
            cur.grid_levels += 1
            if r.lot is not None:
                cur.total_lots = r.total_lots if r.total_lots is not None \
                    else round((cur.total_lots or 0.0) + r.lot, 8)
            continue

        if cur is None:
            continue  # events outside any cycle

        cur.events.append(r.to_dict())
        if r.side and cur.direction == UNKNOWN:
            cur.direction = r.side
        if ev == EVENT_PARTIAL_CLOSE:
            pl = r.basket_pl if r.basket_pl is not None else r.floating_pl
            if pl is not None:
                realized = round(realized + pl, 8)
                cur.realized_profit = realized
        elif ev == EVENT_EMERGENCY:
            pl = r.basket_pl if r.basket_pl is not None else r.floating_pl
            if pl is not None:
                cur.floating_profit = pl
            close_active(EMERGENCY_CLOSED, EVENT_EMERGENCY, r)
            continue
        elif ev in (EVENT_BASKET_CLOSE, EVENT_FRIDAY_STOP, EVENT_DAILY_TARGET):
            pl = r.basket_pl if r.basket_pl is not None else r.floating_pl
            if ev == EVENT_BASKET_CLOSE and pl is not None:
                cur.basket_profit = pl
            elif pl is not None:
                cur.floating_profit = pl
            close_active(CLOSED, ev, r)
            continue
        elif ev in (EVENT_RESUME, EVENT_UNKNOWN):
            continue  # informational for cycle accounting
        # carry latest observed totals when present
        if r.total_lots is not None:
            cur.total_lots = r.total_lots
        if r.floating_pl is not None:
            cur.floating_profit = r.floating_pl
        if r.price is not None:
            cur.end_price = r.price
        if r.timestamp:
            cur.end_time = r.timestamp

    if cur is not None:
        cur.notes = (cur.notes + " Observation window ended before a terminal "
                     "event; status is OPEN as of the last record.").strip()
        cycles.append(cur)
    return cycles


def c_symbol_missing(c: Cycle) -> bool:
    return c.symbol in ("", UNKNOWN)


def model_cycle(config, profile, rules, side: str, levels: int,
                start_price: Optional[float] = None,
                cycle_id: str = "MODEL-1") -> Cycle:
    """Build a MODEL cycle snapshot from the existing core calculations.

    Uses core.calculations.build_side_positions only - no new formula.
    The cycle is a depth snapshot (model lifecycle is not timeline-simulated
    in this phase), labeled source='model' with the MODEL rule note.
    """
    from core import calculations as c  # local import keeps module load clean

    p0 = float(start_price if start_price is not None else profile.reference_price)
    positions, _ = c.build_side_positions(config, side, p0, levels, rules, profile)
    lots = [l for _, _, l in positions]
    entries = [e for _, e, _ in positions]
    return Cycle(
        cycle_id=cycle_id,
        symbol=profile.name,
        direction=side,
        start_time="",
        start_price=entries[0] if entries else None,
        end_price=entries[-1] if entries else None,
        initial_lot=lots[0] if lots else None,
        total_lots=round(sum(lots), 8) if lots else None,
        grid_levels=len(lots),
        status=OPEN,
        source="model",
        notes=("MODEL cycle snapshot from core.calculations at depth "
               f"{levels}. {CYCLE_START_RULE} {CYCLE_END_RULE}"),
        events=[{"event": EVENT_OPEN_POSITION if i == 0 else EVENT_ADD_GRID,
                 "side": side, "level": i + 1, "lot": lots[i], "price": entries[i]}
                for i in range(len(lots))],
    )


def build_cycle_timeline(cycle: Cycle) -> dict:
    """Timeline rows for one cycle from its recorded events.

    Never fills events that do not exist: a missing start entry, a missing
    terminal event, or missing timestamps mark the timeline INCOMPLETE.
    Every row carries whatever fields the source actually recorded
    (None = UNKNOWN).
    """
    rows = []
    for seq, e in enumerate(cycle.events, start=1):
        rows.append({
            "seq": seq,
            "timestamp": e.get("timestamp") or None,
            "event": e.get("event"),
            "position_count": e.get("position_count"),
            "total_lots": e.get("total_lots"),
            "floating_pl": e.get("floating_pl"),
            "realized_pl": e.get("basket_pl"),
            "equity": e.get("equity"),
            "margin": e.get("margin"),
            "drawdown": e.get("drawdown"),
        })
    has_start = bool(cycle.events) and cycle.events[0].get("event") in (
        EVENT_NEW_CYCLE, EVENT_OPEN_POSITION, EVENT_ADD_GRID)
    has_entry = any(e.get("event") in (EVENT_OPEN_POSITION, EVENT_ADD_GRID)
                    for e in cycle.events)
    has_terminal = cycle.status in (CLOSED, EMERGENCY_CLOSED)
    has_timestamps = all(r["timestamp"] for r in rows)
    status = TIMELINE_COMPLETE if (has_start and has_entry and has_terminal
                                   and has_timestamps) else TIMELINE_INCOMPLETE
    missing = []
    if not has_start:
        missing.append("start event")
    if not has_entry:
        missing.append("entry event")
    if not has_terminal:
        missing.append("terminal event")
    if not has_timestamps:
        missing.append("timestamps")
    return {
        "schema": TIMELINE_SCHEMA,
        "cycle_id": cycle.cycle_id,
        "status": status,
        "missing": missing,
        "cycle_status": cycle.status,
        "close_reason": cycle.close_reason or None,
        "direction": cycle.direction,
        "grid_levels": cycle.grid_levels,
        "rows": rows,
    }


def build_cycle_timelines(records: List[BehaviorRecord]) -> List[dict]:
    return [build_cycle_timeline(c) for c in build_cycles_from_records(records)]
