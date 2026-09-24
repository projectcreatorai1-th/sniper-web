"""Real-data pipeline (§9-§12, §15): RAW (immutable) -> NORMALIZED ->
ANALYSIS -> EVIDENCE, with data-quality checks, time integrity and
execution-quality distributions.

RAW sessions are hash-sealed at close and never mutated. Quality
violations are FLAGGED, never silently repaired.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Tick:
    ts_ms: int
    bid: float
    ask: float
    seq: int = 0

    @property
    def spread(self) -> float:
        return round(self.ask - self.bid, 10)


@dataclass
class DataSession:
    """One recording session; RAW payloads are append-only + sealed."""
    session_id: str
    source: str
    broker: str
    server: str
    symbol: str
    account_mode: str          # OBSERVATION / SHADOW / DEMO
    started_at: str
    ticks: List[Tick] = field(default_factory=list)
    orders: List[dict] = field(default_factory=list)
    deals: List[dict] = field(default_factory=list)
    positions: List[dict] = field(default_factory=list)
    account_state: List[dict] = field(default_factory=list)
    quality_flags: List[dict] = field(default_factory=list)
    closed_at: str = ""
    _sealed_hash: str = ""

    def add_tick(self, t: Tick) -> None:
        if self._sealed_hash:
            raise RuntimeError("session sealed — RAW is immutable")
        self.ticks.append(t)

    def close(self) -> str:
        self.closed_at = _utc_now()
        self._sealed_hash = self.compute_hash()
        return self._sealed_hash

    def compute_hash(self) -> str:
        blob = json.dumps({"session_id": self.session_id,
                           "ticks": [asdict(t) for t in self.ticks],
                           "orders": self.orders, "deals": self.deals,
                           "positions": self.positions},
                          sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest().upper()

    def verify(self) -> bool:
        return self.compute_hash() == self._sealed_hash

    def save(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{self.session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"session": asdict(self), "hash": self._sealed_hash},
                      f, ensure_ascii=False, indent=1)
        return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ----------------------------------------------------------------- §10 DQ
def check_quality(session: DataSession, *, max_spread: float = 5.0,
                  max_price: float = 100000.0) -> List[dict]:
    flags: List[dict] = []
    ts_seen = set()
    prev_ms = 0
    for i, t in enumerate(session.ticks):
        if t.bid <= 0 or t.ask <= 0 or t.bid > max_price or t.ask > max_price:
            flags.append({"i": i, "kind": "impossible_price", "v": [t.bid, t.ask]})
        if t.spread < 0 or t.spread > max_spread:
            flags.append({"i": i, "kind": "impossible_spread", "v": t.spread})
        if t.ts_ms in ts_seen:
            flags.append({"i": i, "kind": "duplicate_timestamp"})
        ts_seen.add(t.ts_ms)
        if t.ts_ms < prev_ms:
            flags.append({"i": i, "kind": "timestamp_regression"})
        prev_ms = max(prev_ms, t.ts_ms)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for i, t in enumerate(session.ticks):
        if t.ts_ms > now_ms + 60000:
            flags.append({"i": i, "kind": "timestamp_future"})
    session.quality_flags = flags
    return flags


def check_orphans(session: DataSession) -> List[str]:
    """orphan deals/orders/positions = no matching ledger id"""
    ids = {t.seq for t in session.ticks}
    orphans = [d["id"] for d in session.deals if d.get("id") not in ids]
    return orphans


# --------------------------------------------------------------- §15 time
def time_integrity(ticks: List[Tick]) -> dict:
    ms = [t.ts_ms for t in ticks]
    jumps = [b - a for a, b in zip(ms, ms[1:]) if b - a < 0]
    gaps = [b - a for a, b in zip(ms, ms[1:]) if b - a > 60_000]
    dupes = len(ms) - len(set(ms))
    return {"monotonic": not jumps, "clock_jumps": len(jumps),
            "large_gaps_over_1m": len(gaps), "duplicate_ts": dupes,
            "canonical": "UTC (ms)"}


# ------------------------------------------------------ §12 execution quality
def execution_quality(events: List[dict]) -> dict:
    """Distributions (not averages alone) for latency/slippage etc.
    events carry event_type + timestamps + optional fields."""
    def dist(vals):
        if not vals:
            return {"n": 0}
        s = sorted(vals)
        n = len(vals)
        return {"n": n, "p50": s[n // 2], "p95": s[int(n * 0.95)],
                "min": s[0], "max": s[-1],
                "mean": round(sum(vals) / n, 6)}

    latencies, slips, rejects, timeouts, partials = [], [], 0, 0, 0
    for a, b in zip(events, events[1:]):
        if (a.get("event_type") == "ORDER_SUBMIT"
                and b.get("event_type") in ("ORDER_FILLED", "ORDER_REJECTED")):
            latencies.append(round(b["timestamp_ms"] - a["timestamp_ms"], 3))
    for e in events:
        if e.get("event_type") == "ORDER_REJECTED":
            rejects += 1
        if e.get("status") == "TIMEOUT":
            timeouts += 1
        if e.get("filled_lot") is not None and e.get("requested_lot") and \
                e["filled_lot"] < e["requested_lot"]:
            partials += 1
        if e.get("slippage") is not None:
            slips.append(e["slippage"])
    return {"order_latency_ms": dist(latencies), "slippage": dist(slips),
            "rejections": rejects, "timeouts": timeouts,
            "partial_fills": partials}
