"""Immutable cycle reconstruction engine with per-cycle confidence.

Walks the open/close event timeline of closed positions:
  cycle = all positions opened while the open-count > 0; ends at zero.
  closes sort BEFORE opens at identical timestamps (EA closes the basket,
  sees flat, then opens the next pair).

Each reconstructed cycle is an immutable record with:
  - initial entries / grid entries (per side)
  - partial events (position closes while basket continues)
  - close events (deal-level, matched by time+side+volume)
  - basket close summary
  - confidence + anomaly flags (ambiguous cycles must not be used as
    hard evidence)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

FMT = "%Y.%m.%d %H:%M:%S"

CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"

FLAG_TRUNCATED_START = "TRUNCATED_AT_REPORT_START"
FLAG_STILL_OPEN = "STILL_OPEN_AT_EXPORT"
FLAG_UNPAIRED_START = "UNPAIRED_START"          # first two entries same side
FLAG_ANOMALOUS_LOTS = "ANOMALOUS_LOTS"          # lots off the floor ladder
FLAG_NEGATIVE_CLOSE = "NEGATIVE_CLOSE"          # basket closed at a loss
FLAG_DEEP_GRID = "DEEP_GRID"                    # >= 10 levels one side
FLAG_MULTI_BURST_END = "MULTI_BURST_END"        # final close split > 5s apart


@dataclass(frozen=True)
class PartialEvent:
    time: str
    ticket: str
    side: str
    volume: float
    level_hint: int          # 1-based index of the position on its side ladder
    profit: float
    commission: float
    swap: float
    remaining_open: int
    deal_id: str = ""


@dataclass(frozen=True)
class CloseEvent:
    time: str
    ticket: str
    side: str
    volume: float
    profit: float
    deal_id: str = ""


@dataclass(frozen=True)
class Cycle:
    cycle_id: str
    account_id: str
    symbol: str
    start_time: str
    end_time: str
    initial_entries: Tuple[dict, ...]     # first BUY+SELL pair (or fewer)
    grid_entries: Tuple[dict, ...]        # all later entries
    partial_events: Tuple[PartialEvent, ...]
    close_events: Tuple[CloseEvent, ...]
    basket_close: dict                    # aggregate summary
    confidence: str
    flags: Tuple[str, ...]

    @property
    def members(self) -> List[dict]:
        return list(self.initial_entries) + list(self.grid_entries)

    @property
    def is_ambiguous(self) -> bool:
        return self.confidence == CONF_LOW


def _member(p) -> dict:
    return {"ticket": p.ticket, "side": p.side, "volume": p.volume,
            "open_time": p.open_time, "open_price": p.open_price,
            "close_time": p.close_time, "close_price": p.close_price,
            "profit": p.profit, "commission": p.commission, "swap": p.swap}


def _lot_ladder_ok(seq: List[float]) -> bool:
    """Floor ladder check: lot(n) = floor(0.1*1.1^(n-1)/0.01)*0.01."""
    import math
    for lvl, v in enumerate(seq, 1):
        raw = 0.1 * (1.1 ** (lvl - 1))
        exp = round(math.floor(raw / 0.01 + 1e-9) * 0.01, 2)
        if abs(v - exp) > 0.005:
            return False
    return True


def reconstruct_cycles(report) -> List[Cycle]:
    positions = sorted(report.positions,
                       key=lambda p: (p.open_time, p.ticket))
    deals_by_key = {}
    for d in report.deals:
        if d.direction == "out":
            deals_by_key.setdefault((d.time, d.side, round(d.volume, 2)), d)

    events = []
    for idx, p in enumerate(positions):
        events.append((p.open_time, 1, idx))
        if p.close_time:
            events.append((p.close_time, 0, idx))
    events.sort()

    raw_cycles = []
    current: List[int] = []
    open_count = 0
    partial_idx: List[Tuple[str, int, int]] = []   # (time, idx, remaining)
    for ts, kind, idx in events:
        if kind == 1:
            current.append(idx)
            open_count += 1
        else:
            open_count -= 1
            if open_count > 0:
                partial_idx.append((ts, idx, open_count))
            elif open_count == 0 and current:
                raw_cycles.append((list(current), list(partial_idx), False))
                current, partial_idx = [], []
    if current:
        raw_cycles.append((list(current), list(partial_idx), True))

    cycles: List[Cycle] = []
    for ci, (idxs, parts, still_open) in enumerate(raw_cycles):
        members = [_member(positions[i]) for i in idxs]
        members.sort(key=lambda m: (m["open_time"], m["ticket"]))

        first_two = members[:2]
        paired_start = (len(first_two) == 2
                        and first_two[0]["side"] != first_two[1]["side"])
        initial = tuple(first_two) if paired_start else tuple(first_two[:1])
        grid = tuple(members[len(initial):])

        # per-side ladder for level hints / anomaly detection
        side_seq = {"BUY": [], "SELL": []}
        side_pos = {"BUY": [], "SELL": []}
        for m in members:
            side_seq[m["side"]].append(m["volume"])
            side_pos[m["side"]].append(m)

        partial_events = []
        for ts, idx, remaining in parts:
            p = positions[idx]
            lvl = side_pos[p.side].index(_member(p)) + 1 if _member(p) in side_pos[p.side] else 0
            d = deals_by_key.get((ts, p.side, round(p.volume, 2)))
            partial_events.append(PartialEvent(
                time=ts, ticket=p.ticket, side=p.side, volume=p.volume,
                level_hint=lvl, profit=p.profit, commission=p.commission,
                swap=p.swap, remaining_open=remaining,
                deal_id=d.deal_id if d else ""))

        close_events = []
        for m in members:
            if not m["close_time"]:
                continue
            key = (m["close_time"], "SELL" if m["side"] == "BUY" else "BUY",
                   round(m["volume"], 2))
            d = deals_by_key.get(key)
            close_events.append(CloseEvent(
                time=m["close_time"], ticket=m["ticket"], side=m["side"],
                volume=m["volume"], profit=m["profit"],
                deal_id=d.deal_id if d else ""))
        close_events.sort(key=lambda c: (c.time, c.ticket))

        closes = [m["close_time"] for m in members if m["close_time"]]
        end_time = max(closes) if closes else ""
        gross = sum(m["profit"] for m in members)
        net = gross + sum(m["commission"] + m["swap"] for m in members)
        max_lvl = max(len(v) for v in side_seq.values()) if members else 0
        lots = sum(m["volume"] for m in members)
        dur_s = ((datetime.strptime(end_time, FMT) -
                  datetime.strptime(members[0]["open_time"], FMT)).total_seconds()
                 if end_time else 0.0)
        burst_split = False
        if len(close_events) >= 2:
            from core.forensics.basket_forensics import burst_gap_seconds
            times = [datetime.strptime(c.time, FMT) for c in close_events]
            burst_split = any((b - a).total_seconds() > burst_gap_seconds()
                              for a, b in zip(times, times[1:]))

        flags = []
        if ci == 0:
            flags.append(FLAG_TRUNCATED_START)
        if still_open:
            flags.append(FLAG_STILL_OPEN)
        if not paired_start:
            flags.append(FLAG_UNPAIRED_START)
        if not _lot_ladder_ok(side_seq["BUY"]) or not _lot_ladder_ok(side_seq["SELL"]):
            flags.append(FLAG_ANOMALOUS_LOTS)
        if gross < -0.005:
            flags.append(FLAG_NEGATIVE_CLOSE)
        if max_lvl >= 10:
            flags.append(FLAG_DEEP_GRID)
        if burst_split:
            flags.append(FLAG_MULTI_BURST_END)

        if still_open or (ci == 0 and len(members) < 2):
            conf = CONF_LOW
        elif flags and (FLAG_ANOMALOUS_LOTS in flags or FLAG_UNPAIRED_START in flags
                        or FLAG_MULTI_BURST_END in flags):
            conf = CONF_LOW
        elif flags:
            conf = CONF_MEDIUM
        else:
            conf = CONF_HIGH

        cycles.append(Cycle(
            cycle_id=f"{report.account_id}-C{ci:04d}",
            account_id=report.account_id, symbol="GOLDmicro",
            start_time=members[0]["open_time"], end_time=end_time,
            initial_entries=initial, grid_entries=grid,
            partial_events=tuple(partial_events),
            close_events=tuple(close_events),
            basket_close={"gross": round(gross, 2), "net": round(net, 2),
                          "positions": len(members), "total_lots": round(lots, 2),
                          "max_level": max_lvl,
                          "duration_s": dur_s,
                          "next_cycle_gap_s": None},
            confidence=conf, flags=tuple(flags)))

    # fill next-cycle gaps
    for a, b in zip(cycles, cycles[1:]):
        if a.end_time and b.start_time:
            gap = (datetime.strptime(b.start_time, FMT) -
                   datetime.strptime(a.end_time, FMT)).total_seconds()
            a.basket_close["next_cycle_gap_s"] = gap
    return cycles
