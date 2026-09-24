"""MT5 Observation Sessions (Phase 2).

An ObservationSession holds REAL MT5 data imported for behavior
verification. It is deliberately SEPARATE from any simulation state:

    ObservationSession  = what the EA actually did (observed evidence)
    Simulation          = what the model computes (core calculators)

Import pipeline feeds the ONE canonical event model (mt5_adapters.
BehaviorRecord) - no per-adapter normalization variants. Import results
report exactly what was read/imported/rejected/mapped. Unknown stays
UNKNOWN (None), never 0.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

from core.mt5_adapters import (
    _CSV_ALIASES,
    BehaviorRecord,
    CSVAdapter,
    LogAdapter,
    TesterReportAdapter,
)

SCHEMA = "SNIPER_OBSERVATION_SESSION_V1"

# observation sources (distinct from evidence source types where useful)
SRC_MT5_JOURNAL = "MT5_JOURNAL"
SRC_MT5_CSV = "MT5_CSV"
SRC_MT5_TESTER = "MT5_TESTER"
SRC_MANUAL = "MANUAL_OBSERVATION"
SRC_OTHER = "OTHER"
OBSERVATION_SOURCES = (SRC_MT5_JOURNAL, SRC_MT5_CSV, SRC_MT5_TESTER,
                       SRC_MANUAL, SRC_OTHER)


@dataclass
class ObservationSession:
    session_id: str = ""
    ea_version: str = "1.68"
    environment_profile_id: str = ""
    symbol: str = ""
    timeframe: str = ""
    broker: str = ""
    account_type: str = ""
    initial_balance: Optional[float] = None
    start_time: str = ""
    end_time: str = ""
    parameters: Dict[str, object] = field(default_factory=dict)  # EAConfig dict
    source_type: str = SRC_OTHER
    source_reference: str = ""
    notes: str = ""
    created_at: str = ""
    events: List[BehaviorRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d

    @classmethod
    def new(cls, **kwargs) -> "ObservationSession":
        sid = "OBS-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        s = cls(session_id=sid, created_at=datetime.now().isoformat(timespec="seconds"))
        for k, v in kwargs.items():
            if hasattr(s, k) and v is not None:
                setattr(s, k, v)
        if s.source_type not in OBSERVATION_SOURCES:
            raise ValueError(f"source_type must be one of {OBSERVATION_SOURCES}")
        return s

    @classmethod
    def from_dict(cls, d: dict) -> "ObservationSession":
        s = cls(session_id=d.get("session_id", "UNKNOWN"))
        for k, v in d.items():
            if k in ("schema", "session_id", "events"):
                continue
            if hasattr(s, k) and v is not None:
                setattr(s, k, v)
        s.events = [BehaviorRecord.from_dict(e) for e in (d.get("events") or [])]
        return s

    def event_summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.events:
            counts[e.event] = counts.get(e.event, 0) + 1
        return counts


class ObservationSessionStore:
    """Persistence under data/observation_sessions/<session_id>.json."""

    def __init__(self, directory: Optional[str] = None):
        if directory is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            directory = os.path.join(base, "observation_sessions")
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def _path(self, session_id: str) -> str:
        return os.path.join(self.directory, f"{session_id}.json")

    def save(self, session: ObservationSession) -> None:
        with open(self._path(session.session_id), "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self, session_id: str) -> ObservationSession:
        path = self._path(session_id)
        if not os.path.exists(path):
            raise KeyError(session_id)
        with open(path, "r", encoding="utf-8") as f:
            return ObservationSession.from_dict(json.load(f))

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if os.path.exists(path):
            os.remove(path)

    def list_sessions(self) -> List[str]:
        return sorted(os.path.splitext(f)[0] for f in os.listdir(self.directory)
                      if f.endswith(".json"))


# ---------------------------------------------------------------------------
# Import with reporting (mapping layer on top of the ONE canonical schema)
# ---------------------------------------------------------------------------
@dataclass
class ImportResult:
    rows_read: int = 0
    rows_imported: int = 0
    rows_rejected: int = 0
    unknown_columns: List[str] = field(default_factory=list)
    mapping_used: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    source_kind: str = SRC_MT5_CSV

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = "SNIPER_IMPORT_RESULT_V1"
        return d


def _read_lines(path: str):
    from core.backtest_io import _read_text
    return _read_text(path).splitlines()


def analyze_csv_mapping(header_cells: List[str],
                        user_mapping: Optional[Dict[str, str]] = None) -> tuple:
    """Resolve the canonical mapping for a header row.

    user_mapping overrides aliases: {canonical_field: column_name}.
    Returns (colmap, unknown_columns, mapping_used).
    """
    colmap: Dict[str, int] = {}
    mapping_used: Dict[str, str] = {}
    lowered = [c.strip().lower() for c in header_cells]
    user = {k.lower(): v for k, v in (user_mapping or {}).items()}
    for canonical, aliases in _CSV_ALIASES.items():
        # 1) explicit user mapping wins
        if canonical in user:
            want = user[canonical].strip().lower()
            if want in lowered:
                colmap[canonical] = lowered.index(want)
                mapping_used[canonical] = user[canonical]
                continue
        # 2) standard aliases (same table the CSVAdapter uses - single source)
        for idx, col in enumerate(lowered):
            if col in aliases and canonical not in colmap:
                colmap[canonical] = idx
                mapping_used[canonical] = col
                break
    known = set()
    for aliases in _CSV_ALIASES.values():
        known.update(aliases)
    unknown = [c for c in header_cells if c.strip() and c.strip().lower() not in known]
    return colmap, unknown, mapping_used


def import_csv(path: str, user_mapping: Optional[Dict[str, str]] = None,
               symbol: str = "") -> tuple:
    """Import a behavior CSV into canonical events with a full report.

    Same alias table as CSVAdapter (no second normalizer). Rows without a
    timestamp are rejected (never guessed); exact duplicates are reported.
    """
    lines = [ln for ln in _read_lines(path) if ln.strip()]
    result = ImportResult()
    if not lines:
        result.warnings.append("empty file")
        return [], result

    first = lines[0]
    delim = "\t" if first.count("\t") >= max(first.count(","), first.count(";")) else \
        (";" if first.count(";") > first.count(",") else ",")
    header = [c.strip() for c in first.split(delim)]
    colmap, unknown, mapping_used = analyze_csv_mapping(header, user_mapping)
    result.unknown_columns = unknown
    result.mapping_used = mapping_used
    if "timestamp" not in colmap and "event" not in colmap:
        result.warnings.append("no timestamp/event column - not behavior data")
        return [], result

    def g(cells, key):
        idx = colmap.get(key)
        return cells[idx] if idx is not None and idx < len(cells) else ""

    def num(v):
        v = (v or "").strip().replace(",", "")
        if not v:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    records: List[BehaviorRecord] = []
    seen = set()
    dup = 0
    for line in lines[1:]:
        result.rows_read += 1
        cells = [c.strip() for c in line.split(delim)]
        ts = g(cells, "timestamp")
        if not ts:
            result.rows_rejected += 1
            if result.rows_rejected <= 5:
                result.warnings.append(f"row {result.rows_read}: missing timestamp - rejected")
            continue
        from core.mt5_adapters import normalize_event
        ev = normalize_event(g(cells, "event"))
        key = (ts, ev, g(cells, "ticket"), g(cells, "side"), g(cells, "lot"))
        if key in seen:
            dup += 1
            result.rows_rejected += 1
            continue
        seen.add(key)
        side = g(cells, "side").upper()
        lvl = num(g(cells, "grid_level"))
        pc = num(g(cells, "position_count"))
        records.append(BehaviorRecord(
            timestamp=ts, symbol=g(cells, "symbol") or symbol,
            event=ev, side=side if side in ("BUY", "SELL") else "",
            ticket=g(cells, "ticket"),
            grid_level=int(lvl) if lvl is not None else None,
            lot=num(g(cells, "lot")), price=num(g(cells, "price")),
            balance=num(g(cells, "balance")), equity=num(g(cells, "equity")),
            margin=num(g(cells, "margin")), free_margin=num(g(cells, "free_margin")),
            floating_pl=num(g(cells, "floating_pl")), basket_pl=num(g(cells, "basket_pl")),
            position_count=int(pc) if pc is not None else None,
            total_lots=num(g(cells, "total_lots")), drawdown=num(g(cells, "drawdown")),
            commission=num(g(cells, "commission")), swap=num(g(cells, "swap")),
            spread=num(g(cells, "spread")),
            source="csv-import", confidence="MEDIUM",
        ))
        result.rows_imported += 1
    if dup:
        result.warnings.append(f"{dup} duplicate row(s) skipped")
    if unknown:
        result.warnings.append(f"unknown column(s) ignored: {', '.join(unknown)}")
    return records, result


def import_file(path: str, source_kind: str,
                user_mapping: Optional[Dict[str, str]] = None) -> tuple:
    """Route a file to the right importer; every path feeds the canonical
    BehaviorRecord model (adapters unchanged in behavior)."""
    if source_kind in (SRC_MT5_CSV, "csv"):
        return import_csv(path, user_mapping)
    if source_kind in (SRC_MT5_TESTER, "tester"):
        adapter = TesterReportAdapter(path)
        records = adapter.load()
        return records, ImportResult(rows_read=len(records), rows_imported=len(records),
                                     source_kind=SRC_MT5_TESTER,
                                     mapping_used={"adapter": "TesterReportAdapter"},
                                     warnings=["events derived from tester-report deals "
                                               "(derived, not EA-logged events)"])
    if source_kind in (SRC_MT5_JOURNAL, "log"):
        adapter = LogAdapter(path)
        records = adapter.load()
        return records, ImportResult(rows_read=len(records), rows_imported=len(records),
                                     source_kind=SRC_MT5_JOURNAL,
                                     mapping_used={"adapter": "LogAdapter"},
                                     warnings=["keyword-classified log lines; ambiguous "
                                               "lines stay UNKNOWN"])
    raise ValueError(f"unsupported source_kind: {source_kind}")


# ---------------------------------------------------------------------------
# Controlled test plan templates (what to capture in real MT5 sessions)
# ---------------------------------------------------------------------------
CONTROLLED_TEST_PLANS: Dict[str, dict] = {
    "TEST_A_LOT": {
        "name": "TEST A — Lot progression",
        "capture": ["Position 1..5 lots (10 levels if possible)",
                    "exact lot values as shown in MT5"],
        "fields": ["timestamp", "side", "grid_level", "lot", "price"],
    },
    "TEST_B_GRID": {
        "name": "TEST B — Grid spacing",
        "capture": ["Entry price + grid 2..5+ prices",
                    "computed observed price distance between adds"],
        "fields": ["timestamp", "side", "grid_level", "price"],
    },
    "TEST_C_BUYSELL": {
        "name": "TEST C — Buy/Sell relationship",
        "capture": ["run BUY only", "run SELL only", "run both",
                    "if the environment cannot do one, record the reason"],
        "fields": ["timestamp", "side", "event", "lot", "price"],
    },
    "TEST_D_BASKET": {
        "name": "TEST D — Basket close",
        "capture": ["entry + grids", "floating P/L before close",
                    "BasketCloseAllUSD used", "close event", "final P/L",
                    "commission/swap if shown"],
        "fields": ["timestamp", "event", "basket_pl", "commission", "swap",
                   "balance"],
    },
    "TEST_E_PARTIAL": {
        "name": "TEST E — Partial close",
        "capture": ["lots/position count/exposure before trigger",
                    "trigger moment", "the same after partial"],
        "fields": ["timestamp", "event", "lot", "total_lots",
                   "position_count", "floating_pl", "basket_pl"],
    },
    "TEST_F_EMERGENCY": {
        "name": "TEST F — Emergency",
        "capture": ["reference price (cycle start)", "trigger price",
                    "distance", "positions before/after", "equity",
                    "floating loss", "close behavior"],
        "fields": ["timestamp", "event", "price", "position_count",
                   "equity", "floating_pl"],
    },
}
