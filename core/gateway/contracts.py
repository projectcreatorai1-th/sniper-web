"""SNIPER Analyzer Gateway Client — contracts (§5, §7, §11).

Authority (§0): SNIPER = Research/Signal/Evidence.
The Gateway = Transport only. SNIPER NEVER sends orders to MT5.

Signal schema + Event envelope + Contract version aligned with
1144 Trading OS event contracts (CONTRACT_VERSION 1.4.0, correlation_id
pattern, immutable events).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

GATEWAY_CONTRACT_VERSION = "1.0.0"
SIGNAL_SCHEMA_VERSION = "1.0.0"
EVENT_SCHEMA_VERSION = "1.0.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def canonical_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str).encode()).hexdigest().upper()


# ============================== Signal (§7) ==============================
class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


class SignalType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    FILTER = "FILTER"
    ALERT = "ALERT"
    ANALYSIS = "ANALYSIS"


@dataclass(frozen=True)
class Signal:
    signal_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    direction: str             # SignalDirection
    signal_type: str           # SignalType
    entry_reference: float
    stop_reference: float
    target_reference: float
    confidence: float
    created_at: str
    expires_at: str
    analysis_version: str
    dataset_version: str
    backtest_id: str = ""
    evidence_id: str = ""
    evidence_hash: str = ""
    correlation_id: str = ""
    schema_version: str = SIGNAL_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    def hash(self) -> str:
        return canonical_hash(self.to_dict())

    def is_expired(self, now: Optional[str] = None) -> bool:
        check = now or utc_now_iso()
        return check > self.expires_at


# ============================ Event envelope (§11) ============================
@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    schema_version: str
    created_at: str
    source: str                # e.g. "SNIPER-ANALYZER"
    target: str                # e.g. "1144-GATEWAY"
    sequence: int
    correlation_id: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ========================== Signal lifecycle (§9) ==========================
class SignalLifecycle(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"
    RECEIVED_BY_GATEWAY = "RECEIVED_BY_GATEWAY"
    ACCEPTED_BY_EA = "ACCEPTED_BY_EA"
    REJECTED_BY_RISK = "REJECTED_BY_RISK"
    EXECUTION_REQUESTED = "EXECUTION_REQUESTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


# ========================== Connection state (§3) ==========================
class ConnectionState(str, Enum):
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


# ======================== Contract handshake (§5) ========================
@dataclass(frozen=True)
class ContractInfo:
    protocol_version: str = "1.0"
    contract_version: str = GATEWAY_CONTRACT_VERSION
    client_version: str = ""
    gateway_version: str = ""
    supported_features: tuple = ("signal.publish", "event.subscribe",
                                  "state.snapshot", "heartbeat",
                                  "reconciliation")
    capabilities: tuple = ("research", "backtest", "analysis", "replay")


@dataclass(frozen=True)
class ContractMismatch:
    required_version: str
    actual_version: str
    resolution: str
    reason: str


# ======================== Evidence package (§15) ========================
@dataclass(frozen=True)
class EvidencePackage:
    signal_id: str
    analysis_id: str
    strategy_id: str
    strategy_version: str
    dataset_id: str
    dataset_version: str
    backtest_id: str
    metrics: Dict[str, Any]
    parameters: Dict[str, Any]
    created_at: str
    evidence_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


# ========================= Execution feedback (§17) =========================
@dataclass(frozen=True)
class ExecutionFeedback:
    execution_id: str
    signal_id: str
    correlation_id: str
    symbol: str
    requested_price: float
    executed_price: float
    volume: float
    fill_count: int
    slippage: float
    spread: float
    latency_ms: float
    created_at: str
    executed_at: str
    status: str
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ============================ Gateway events (§10) ============================
GATEWAY_EVENTS = frozenset({
    "GATEWAY_CONNECTED", "GATEWAY_DISCONNECTED",
    "EA_CONNECTED", "EA_DISCONNECTED", "EA_HEARTBEAT",
    "MT5_CONNECTED", "MT5_DISCONNECTED",
    "MARKET_DATA_UPDATED",
    "POSITION_OPENED", "POSITION_UPDATED", "POSITION_CLOSED",
    "ORDER_CREATED", "ORDER_SENT", "ORDER_FILLED", "ORDER_REJECTED",
    "ORDER_CANCELLED", "ORDER_EXPIRED", "ORDER_PARTIALLY_FILLED",
    "RISK_UPDATED",
    "SIGNAL_RECEIVED", "SIGNAL_ACCEPTED", "SIGNAL_REJECTED",
    "EXECUTION_RESULT",
    "RECONCILIATION_STARTED", "RECONCILIATION_COMPLETED",
    "RECONCILIATION_FAILED",
})
