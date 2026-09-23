"""Test Sessions (Module 15).

Each session is stored separately under data/sessions/<session_id>.json and
holds session metadata, the EA parameters used, imported data sources,
observed events, and cached comparison results.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

from core.config import EAConfig
from core.mt5_adapters import BehaviorRecord

SESSION_SCHEMA = "SNIPER_TEST_SESSION_V1"


@dataclass
class TestSession:
    session_id: str
    ea_version: str = "1.68"
    symbol: str = ""
    broker: str = ""
    account_type: str = ""            # demo / live / strategy tester
    initial_balance: Optional[float] = None
    start_time: str = ""
    end_time: str = ""
    notes: str = ""
    config: dict = field(default_factory=lambda: EAConfig().to_dict())
    report_files: List[str] = field(default_factory=list)   # imported file paths
    observed_events: List[dict] = field(default_factory=list)
    last_comparison: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SESSION_SCHEMA
        return d

    @classmethod
    def new(cls, **kwargs) -> "TestSession":
        sid = "S" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
        s = cls(session_id=sid)
        for k, v in kwargs.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    @classmethod
    def from_dict(cls, d: dict) -> "TestSession":
        s = cls(session_id=d.get("session_id", "UNKNOWN"))
        for k, v in d.items():
            if k in ("schema", "session_id"):
                continue
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    def events_as_records(self) -> List[BehaviorRecord]:
        return [BehaviorRecord.from_dict(e) for e in self.observed_events]


class SessionStore:
    def __init__(self, directory: Optional[str] = None):
        if directory is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            directory = os.path.join(base, "sessions")
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def _path(self, session_id: str) -> str:
        return os.path.join(self.directory, f"{session_id}.json")

    def save(self, session: TestSession) -> None:
        with open(self._path(session.session_id), "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self, session_id: str) -> TestSession:
        path = self._path(session_id)
        if not os.path.exists(path):
            raise KeyError(session_id)
        with open(path, "r", encoding="utf-8") as f:
            return TestSession.from_dict(json.load(f))

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if os.path.exists(path):
            os.remove(path)

    def list_sessions(self) -> List[str]:
        return sorted(os.path.splitext(f)[0] for f in os.listdir(self.directory)
                      if f.endswith(".json"))

    def load_all(self) -> List[TestSession]:
        return [self.load(sid) for sid in self.list_sessions()]
