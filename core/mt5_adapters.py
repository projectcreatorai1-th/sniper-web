"""MT5 Test Data Pipeline (Module 13).

Adapter interface:

    MT5DataSource
     |-- CSVAdapter          standard-schema CSV (header aliases supported)
     |-- TesterReportAdapter MT5 Strategy Tester report (csv/html/txt) -> events
     |-- LogAdapter          free-form text logs -> events (keyword patterns)
     `-- ManualAdapter       manually entered behavior rows

Every adapter converts data into BehaviorRecord objects using ONE standard
schema. We never assume the EX5 can export data by itself - all sources are
user-provided files or manual entries.

Event types: NEW_CYCLE, OPEN_POSITION, ADD_GRID, PARTIAL_CLOSE, BASKET_CLOSE,
EMERGENCY, FRIDAY_STOP, DAILY_TARGET, RESUME, UNKNOWN.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Protocol

from core.backtest_io import parse_backtest_file

# ---------------------------------------------------------------------------
# Standard schema + event types
# ---------------------------------------------------------------------------
EVENT_NEW_CYCLE = "NEW_CYCLE"
EVENT_OPEN_POSITION = "OPEN_POSITION"
EVENT_ADD_GRID = "ADD_GRID"
EVENT_PARTIAL_CLOSE = "PARTIAL_CLOSE"
EVENT_BASKET_CLOSE = "BASKET_CLOSE"
EVENT_EMERGENCY = "EMERGENCY"
EVENT_FRIDAY_STOP = "FRIDAY_STOP"
EVENT_DAILY_TARGET = "DAILY_TARGET"
EVENT_RESUME = "RESUME"
EVENT_UNKNOWN = "UNKNOWN"

EVENT_TYPES = (EVENT_NEW_CYCLE, EVENT_OPEN_POSITION, EVENT_ADD_GRID,
               EVENT_PARTIAL_CLOSE, EVENT_BASKET_CLOSE, EVENT_EMERGENCY,
               EVENT_FRIDAY_STOP, EVENT_DAILY_TARGET, EVENT_RESUME, EVENT_UNKNOWN)

_SCHEMA_FIELDS = (
    "timestamp", "symbol", "event", "side", "ticket", "grid_level", "lot",
    "price", "balance", "equity", "margin", "free_margin", "floating_pl",
    "basket_pl", "position_count", "total_lots", "drawdown",
)


@dataclass
class BehaviorRecord:
    timestamp: str = ""
    symbol: str = ""
    event: str = EVENT_UNKNOWN
    side: str = ""                    # BUY / SELL / ""
    ticket: str = ""
    grid_level: Optional[int] = None
    lot: Optional[float] = None
    price: Optional[float] = None
    balance: Optional[float] = None
    equity: Optional[float] = None
    margin: Optional[float] = None
    free_margin: Optional[float] = None
    floating_pl: Optional[float] = None
    basket_pl: Optional[float] = None
    position_count: Optional[int] = None
    total_lots: Optional[float] = None
    drawdown: Optional[float] = None
    source: str = ""                  # adapter name
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BehaviorRecord":
        r = cls()
        for k in _SCHEMA_FIELDS + ("source", "note"):
            if k in d and d[k] is not None:
                cur = getattr(r, k)
                v = d[k]
                if isinstance(cur, float) and not isinstance(cur, bool):
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue
                elif isinstance(cur, int) and not isinstance(cur, bool):
                    try:
                        v = int(float(v))
                    except (TypeError, ValueError):
                        continue
                setattr(r, k, v)
        return r


class MT5DataSource(Protocol):
    name: str

    def load(self) -> List[BehaviorRecord]:
        ...


# ---------------------------------------------------------------------------
# CSVAdapter - standard schema CSV with tolerant header aliases
# ---------------------------------------------------------------------------
_CSV_ALIASES = {
    "timestamp": {"timestamp", "time", "datetime", "date"},
    "symbol": {"symbol", "market"},
    "event": {"event", "event_type", "type"},
    "side": {"side", "direction"},
    "ticket": {"ticket", "deal", "deal #", "order"},
    "grid_level": {"grid_level", "level", "grid"},
    "lot": {"lot", "lots", "volume"},
    "price": {"price"},
    "balance": {"balance"},
    "equity": {"equity"},
    "margin": {"margin"},
    "free_margin": {"free_margin", "free margin"},
    "floating_pl": {"floating_pl", "floating", "floating p/l"},
    "basket_pl": {"basket_pl", "basket", "basket p/l"},
    "position_count": {"position_count", "positions", "count"},
    "total_lots": {"total_lots", "total volume"},
    "drawdown": {"drawdown", "dd"},
}

_EVENT_ALIASES = {
    "new_cycle": EVENT_NEW_CYCLE, "cycle": EVENT_NEW_CYCLE, "newcycle": EVENT_NEW_CYCLE,
    "open": EVENT_OPEN_POSITION, "open_position": EVENT_OPEN_POSITION, "first": EVENT_OPEN_POSITION,
    "add": EVENT_ADD_GRID, "add_grid": EVENT_ADD_GRID, "grid": EVENT_ADD_GRID,
    "partial": EVENT_PARTIAL_CLOSE, "partial_close": EVENT_PARTIAL_CLOSE,
    "basket": EVENT_BASKET_CLOSE, "basket_close": EVENT_BASKET_CLOSE, "close_all": EVENT_BASKET_CLOSE,
    "emergency": EVENT_EMERGENCY, "friday": EVENT_FRIDAY_STOP, "friday_stop": EVENT_FRIDAY_STOP,
    "daily_target": EVENT_DAILY_TARGET, "target": EVENT_DAILY_TARGET,
    "resume": EVENT_RESUME,
}


def normalize_event(raw: str) -> str:
    key = (raw or "").strip().lower().replace(" ", "_")
    if not key:
        return EVENT_UNKNOWN
    if key in _EVENT_ALIASES:
        return _EVENT_ALIASES[key]
    if key.upper() in EVENT_TYPES:
        return key.upper()
    return EVENT_UNKNOWN


def _num(v: str) -> Optional[float]:
    if v is None:
        return None
    t = str(v).strip().replace(",", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


class CSVAdapter:
    name = "csv"

    def __init__(self, path: str):
        self.path = path

    def load(self) -> List[BehaviorRecord]:
        from core.backtest_io import _read_text
        text = _read_text(self.path)
        records: List[BehaviorRecord] = []
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return records
        first = lines[0]
        delim = "\t" if first.count("\t") >= max(first.count(","), first.count(";")) else \
            (";" if first.count(";") > first.count(",") else ",")
        header = [c.strip().lower() for c in first.split(delim)]
        colmap = {}
        for idx, col in enumerate(header):
            for canonical, aliases in _CSV_ALIASES.items():
                if col in aliases and canonical not in colmap:
                    colmap[canonical] = idx
        if "timestamp" not in colmap and "event" not in colmap:
            raise ValueError("CSV does not look like behavior/event data "
                             "(no timestamp/event column)")
        for line in lines[1:]:
            cells = [c.strip() for c in line.split(delim)]
            if not cells or all(not c for c in cells):
                continue

            def g(key) -> str:
                idx = colmap.get(key)
                return cells[idx] if idx is not None and idx < len(cells) else ""

            records.append(BehaviorRecord(
                timestamp=g("timestamp"),
                symbol=g("symbol"),
                event=normalize_event(g("event")),
                side=g("side").upper() if g("side").upper() in ("BUY", "SELL") else "",
                ticket=g("ticket"),
                grid_level=int(_num(g("grid_level"))) if _num(g("grid_level")) is not None else None,
                lot=_num(g("lot")),
                price=_num(g("price")),
                balance=_num(g("balance")),
                equity=_num(g("equity")),
                margin=_num(g("margin")),
                free_margin=_num(g("free_margin")),
                floating_pl=_num(g("floating_pl")),
                basket_pl=_num(g("basket_pl")),
                position_count=int(_num(g("position_count"))) if _num(g("position_count")) is not None else None,
                total_lots=_num(g("total_lots")),
                drawdown=_num(g("drawdown")),
                source=self.name,
            ))
        return records


# ---------------------------------------------------------------------------
# TesterReportAdapter - MT5 backtest report -> derived behavior events
# ---------------------------------------------------------------------------
class TesterReportAdapter:
    name = "tester-report"

    def __init__(self, path: str):
        self.path = path

    def load(self) -> List[BehaviorRecord]:
        summary = parse_backtest_file(self.path)
        records: List[BehaviorRecord] = []
        open_lots = 0.0
        position_count = 0
        level = 0
        symbol = summary.symbol or ""
        for d in summary.deals:
            if d.type not in ("buy", "sell"):
                continue
            side = d.type.upper()
            if d.direction in ("in", "inout"):
                position_count += 1
                level += 1
                open_lots = round(open_lots + d.volume, 4)
                event = EVENT_OPEN_POSITION if position_count == 1 else EVENT_ADD_GRID
                records.append(BehaviorRecord(
                    timestamp=d.time, symbol=d.symbol or symbol, event=event,
                    side=side, ticket=d.deal_id or d.order, grid_level=level,
                    lot=d.volume, price=d.price, balance=d.balance,
                    position_count=position_count, total_lots=open_lots,
                    source=self.name,
                    note="derived from tester report deals (entry deals only)",
                ))
            elif d.direction == "out":
                position_count = max(position_count - 1, 0)
                open_lots = round(max(open_lots - d.volume, 0.0), 4)
                records.append(BehaviorRecord(
                    timestamp=d.time, symbol=d.symbol or symbol, event=EVENT_BASKET_CLOSE,
                    side=side, ticket=d.deal_id or d.order, lot=d.volume,
                    price=d.price, balance=d.balance,
                    position_count=position_count, total_lots=open_lots,
                    floating_pl=d.profit,
                    source=self.name,
                    note="derived from tester report deals (exit deal)",
                ))
                if position_count == 0:
                    level = 0
        if not records:
            raise ValueError(
                "report contains no deal rows - behavior events cannot be derived "
                "(HTML summary-only reports have no deals table)")
        return records


# ---------------------------------------------------------------------------
# LogAdapter - keyword-pattern text logs
# ---------------------------------------------------------------------------
import re as _re

# checked in priority order: the first matching pattern wins, so specific
# events (partial/basket/emergency) are not swallowed by generic "open/grid"
_LOG_RULES = [
    (_re.compile(r"friday"), EVENT_FRIDAY_STOP),
    (_re.compile(r"daily\s+target|accum"), EVENT_DAILY_TARGET),
    (_re.compile(r"resume|restart"), EVENT_RESUME),
    (_re.compile(r"emergency"), EVENT_EMERGENCY),
    (_re.compile(r"partial"), EVENT_PARTIAL_CLOSE),
    (_re.compile(r"basket|close\s*all|closeall"), EVENT_BASKET_CLOSE),
    (_re.compile(r"new\s+cycle|cycle\s+start|start\s+cycle"), EVENT_NEW_CYCLE),
    (_re.compile(r"add(?:ed)?|grid|level\s*#?\s*\d+"), EVENT_ADD_GRID),
    (_re.compile(r"open(?:ed)?|first\s+order"), EVENT_OPEN_POSITION),
]
_LOT_RE = _re.compile(r"(?:lot|volume|lots)\s*[:=]?\s*(-?\d+(?:\.\d+)?)")
_PRICE_RE = _re.compile(r"(?:price|at)\s*[:=]?\s*(-?\d+(?:\.\d+)?)")
_LEVEL_RE = _re.compile(r"level\s*#?\s*(\d+)")


class LogAdapter:
    name = "log"

    def __init__(self, path: str):
        self.path = path

    def load(self) -> List[BehaviorRecord]:
        from core.backtest_io import _read_text
        text = _read_text(self.path)
        records: List[BehaviorRecord] = []
        matched_lines = 0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            low = line.lower()
            event = next((ev for rx, ev in _LOG_RULES if rx.search(low)), None)
            if event is None:
                continue
            matched_lines += 1
            m = _LOT_RE.search(low)
            m_lot = float(m.group(1)) if m else None
            m = _PRICE_RE.search(low)
            m_price = float(m.group(1)) if m else None
            m = _LEVEL_RE.search(low)
            m_level = int(m.group(1)) if m else None
            side = ""
            if "buy" in low:
                side = "BUY"
            elif "sell" in low:
                side = "SELL"
            ts = line.split()[0] if line and line[0].isdigit() else ""
            records.append(BehaviorRecord(
                timestamp=ts, event=event, side=side, grid_level=m_level,
                lot=m_lot, price=m_price,
                source=self.name, note=line[:200],
            ))
        if matched_lines == 0:
            raise ValueError("no recognizable event lines in log "
                             "(expected keywords like open/grid/basket/partial/emergency)")
        return records


# ---------------------------------------------------------------------------
# ManualAdapter - in-app manual behavior entries
# ---------------------------------------------------------------------------
class ManualAdapter:
    name = "manual"

    def __init__(self, records: Optional[List[BehaviorRecord]] = None):
        self._records = list(records or [])

    def add(self, record: BehaviorRecord) -> None:
        if record.event not in EVENT_TYPES:
            record.event = normalize_event(record.event)
        self._records.append(record)

    def load(self) -> List[BehaviorRecord]:
        return [r for r in self._records if r.event in EVENT_TYPES]


def load_adapter(path: str, kind: Optional[str] = None) -> MT5DataSource:
    """Factory: pick an adapter by explicit kind or file extension."""
    ext = os.path.splitext(path)[1].lower()
    if kind == "csv" or (kind is None and ext == ".csv"):
        # could be standard-schema csv OR an MT5 tester csv - try schema first
        try:
            adapter = CSVAdapter(path)
            records = adapter.load()
            if records:
                return adapter, records
        except (ValueError, OSError):
            pass
        adapter = TesterReportAdapter(path)
        return adapter, adapter.load()
    if kind == "tester" or (kind is None and ext in (".htm", ".html")):
        adapter = TesterReportAdapter(path)
        return adapter, adapter.load()
    if kind == "log" or (kind is None and ext in (".txt", ".log")):
        adapter = LogAdapter(path)
        return adapter, adapter.load()
    raise ValueError(f"cannot pick adapter for {path} (kind={kind}, ext={ext})")
