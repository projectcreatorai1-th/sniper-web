"""Immutable event records + append-only event log (§15, §17, §35).

Every event carries rule/model/trace references; event ids are unique and
checked; JSON + CSV serialization for deterministic replay and audit.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

FIELDS = ("event_id", "timestamp", "account", "symbol", "cycle_id",
          "basket_id", "position_id", "event_type", "state_before",
          "state_after", "side", "lot", "price", "level", "reason",
          "rule_id", "model_version", "evidence_ref", "execution_mode",
          "trace_id", "hypothesis_id", "config_version")

EVENT_TYPES = (
    "CYCLE_OPEN", "ENTRY", "GRID_ADD", "PARTIAL_CLOSE_INTENT",
    "PARTIAL_CLOSE", "BASKET_CLOSE_INTENT", "BASKET_CLOSE", "CYCLE_END",
    "MODEL_UNCERTAINTY", "RISK_BLOCK", "ORDER_SUBMIT", "ORDER_FILLED",
    "ORDER_REJECTED", "DUPLICATE_EVENT", "STATE_TRANSITION", "ERROR",
    "LIVE_EXECUTION_REQUESTED", "SAFE_STOP", "RECOVERY", "SNAPSHOT",
)


@dataclass(frozen=True)
class Event:
    event_id: str
    timestamp: str
    event_type: str
    state_before: str = ""
    state_after: str = ""
    account: str = ""
    symbol: str = ""
    cycle_id: str = ""
    basket_id: str = ""
    position_id: str = ""
    side: str = ""
    lot: float = 0.0
    price: float = 0.0
    level: int = 0
    reason: str = ""
    rule_id: str = ""
    model_version: str = ""
    evidence_ref: str = ""
    execution_mode: str = ""
    trace_id: str = ""
    hypothesis_id: str = ""
    config_version: str = ""

    def validate(self) -> None:
        if not self.event_id:
            raise ValueError("event_id required")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {self.event_type}")
        if not self.model_version:
            raise ValueError("model_version required on every event")

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class EventLog:
    """Append-only log with uniqueness + optional persistence."""

    def __init__(self, model_version: str, persist_path: Optional[str] = None):
        self.model_version = model_version
        self.persist_path = persist_path
        self._events: List[Event] = []
        self._seen_ids = set()

    def emit(self, **kwargs) -> Event:
        kwargs.setdefault("model_version", self.model_version)
        kwargs.setdefault("timestamp",
                          datetime.now().isoformat(timespec="milliseconds"))
        ev = Event(event_id=kwargs.pop("event_id", self._next_id()),
                   **kwargs)
        ev.validate()
        if ev.event_id in self._seen_ids:
            raise ValueError(f"duplicate event_id: {ev.event_id}")
        self._seen_ids.add(ev.event_id)
        self._events.append(ev)
        if self.persist_path:
            self._append_json_line(ev)
        return ev

    def _next_id(self) -> str:
        return f"E{len(self._events) + 1:08d}"

    def _append_json_line(self, ev: Event) -> None:
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[Event]:
        return list(self._events)

    def by_type(self, event_type: str) -> List[Event]:
        return [e for e in self._events if e.event_type == event_type]

    def by_trace(self, trace_id: str) -> List[Event]:
        return [e for e in self._events if e.trace_id == trace_id]

    def export_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self._events], f,
                      ensure_ascii=False, indent=1)

    def export_csv(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
            for e in self._events:
                w.writerow([getattr(e, k) for k in FIELDS])
