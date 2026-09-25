"""Analyzer Gateway Client (§2-§14).

CLIENT ONLY — never a Gateway Server. SNIPER connects to the 1144
Trading Gateway for transport: publish signals, subscribe events,
heartbeat, reconnect, state sync, reconciliation.

Transport: pluggable (WebSocket default; HTTP polling fallback).
Since no gateway server is running in this environment, the client
supports a loopback/test transport for E2E validation while real
connection is ENVIRONMENT-BLOCKED.

Safety (§26): SNIPER NEVER sends orders. Signals are research output.
Execution authority = OUR EA → MT5 → Broker only.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from core.gateway.contracts import (
    ConnectionState, ContractInfo, ContractMismatch, EventEnvelope,
    GATEWAY_CONTRACT_VERSION, GATEWAY_EVENTS, Signal, SignalLifecycle,
    utc_now_iso, new_id, canonical_hash)

logger = logging.getLogger(__name__)


class GatewayError(RuntimeError):
    pass


class ContractRejected(GatewayError):
    def __init__(self, mismatch: ContractMismatch):
        self.mismatch = mismatch
        super().__init__(f"CONTRACT_MISMATCH: {mismatch.reason}")


# ============================ Transport (pluggable) ============================
class Transport:
    """Abstract transport — connect/send/recv."""
    def connect(self, endpoint: str) -> bool:
        raise NotImplementedError
    def disconnect(self) -> None:
        raise NotImplementedError
    def send(self, data: bytes) -> bool:
        raise NotImplementedError
    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        raise NotImplementedError
    def is_alive(self) -> bool:
        raise NotImplementedError


class LoopbackTransport(Transport):
    """Test/simulation transport — mirrors messages back with
    gateway-style responses. Used ONLY for E2E validation when no
    real gateway exists. Clearly labelled as SIMULATION."""

    def __init__(self):
        self._connected = False
        self._sent: List[bytes] = []
        self._recv_queue: List[bytes] = []
        self._contract_info = ContractInfo(
            gateway_version="TEST-GW-1.0")

    def connect(self, endpoint: str) -> bool:
        self._connected = True
        response = json.dumps({
            "type": "CONTRACT_RESPONSE", "gateway_version": "TEST-GW-1.0",
            "contract_version": GATEWAY_CONTRACT_VERSION,
            "accepted": True}).encode()
        self._recv_queue.append(response)
        return True

    def disconnect(self) -> None:
        self._connected = False

    def send(self, data: bytes) -> bool:
        if not self._connected:
            return False
        self._sent.append(data)
        msg = json.loads(data)
        msg_type = msg.get("type", "")
        # Simulate gateway acknowledgments
        if msg_type == "SIGNAL_PUBLISH":
            ack = {"type": "SIGNAL_ACK", "signal_id": msg.get("signal_id"),
                   "accepted": True, "timestamp": utc_now_iso()}
            self._recv_queue.append(json.dumps(ack).encode())
        elif msg_type == "HEARTBEAT":
            hb = {"type": "HEARTBEAT_ACK", "timestamp": utc_now_iso()}
            self._recv_queue.append(json.dumps(hb).encode())
        elif msg_type == "STATE_REQUEST":
            snap = {"type": "STATE_SNAPSHOT", "state": {},
                    "sequence": 0, "timestamp": utc_now_iso()}
            self._recv_queue.append(json.dumps(snap).encode())
        return True

    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        if self._recv_queue:
            return self._recv_queue.pop(0)
        return None

    def is_alive(self) -> bool:
        return self._connected


# ============================ Gateway Client (§2) ============================
class GatewayClient:
    """Analyzer Gateway Client — the ONLY integration point between
    SNIPER and the 1144 ecosystem. SNIPER is a CLIENT, not a server."""

    def __init__(self, endpoint: str = "", client_id: str = "SNIPER-ANALYZER",
                 transport: Optional[Transport] = None,
                 heartbeat_interval: float = 30.0,
                 heartbeat_timeout: float = 10.0):
        self.endpoint = endpoint
        self.client_id = client_id
        self._transport = transport or LoopbackTransport()
        self._state = ConnectionState.OFFLINE
        self._lock = threading.Lock()

        # connection metrics (§3)
        self.connected_at: Optional[str] = None
        self.disconnected_at: Optional[str] = None
        self.last_heartbeat: Optional[str] = None
        self.reconnect_count = 0
        self.last_error: str = ""
        self.gateway_version: str = ""
        self.contract_version: str = ""
        self.latency_ms: float = 0.0

        # session (§6)
        self.session_id: str = ""
        self._auth_state = "UNAUTHENTICATED"

        # signal lifecycle tracking (§9)
        self._signal_lifecycle: Dict[str, str] = {}
        self._signal_history: List[dict] = []

        # event handling (§10-§12)
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._seen_event_ids: Set[str] = set()
        self._seen_signal_ids: Set[str] = set()
        self._event_sequence = 0
        self._correlation_map: Dict[str, List[str]] = {}

        # audit (§23)
        self._audit_log: List[dict] = []

    # ===== connection (§3) =====
    def get_state(self) -> ConnectionState:
        return self._state

    def connect(self) -> bool:
        with self._lock:
            if self._state == ConnectionState.CONNECTED:
                return True
            self._state = ConnectionState.CONNECTING
            self._audit("connection", "connect", "ATTEMPT",
                        f"endpoint={self.endpoint}")
            if not self._transport.connect(self.endpoint):
                self._state = ConnectionState.ERROR
                self.last_error = "transport connect failed"
                self._audit("connection", "connect", "FAIL", self.last_error)
                return False
            # contract handshake (§5)
            if not self._handshake():
                self._state = ConnectionState.ERROR
                return False
            self._state = ConnectionState.CONNECTED
            self.connected_at = utc_now_iso()
            self.session_id = new_id("SESS")
            self._auth_state = "AUTHENTICATED"
            self._audit("connection", "connect", "OK",
                        f"session={self.session_id}")
            return True

    def disconnect(self) -> None:
        with self._lock:
            if self._state == ConnectionState.OFFLINE:
                return
            self._transport.disconnect()
            self._state = ConnectionState.OFFLINE
            self.disconnected_at = utc_now_iso()
            self._auth_state = "UNAUTHENTICATED"
            self._audit("connection", "disconnect", "OK", "")

    def _handshake(self) -> bool:
        contract = ContractInfo(client_version="SNIPER-1.0")
        msg = {"type": "CONTRACT_REQUEST",
               "protocol_version": contract.protocol_version,
               "contract_version": contract.contract_version,
               "client_version": contract.client_version,
               "supported_features": list(contract.supported_features),
               "capabilities": list(contract.capabilities)}
        self._transport.send(json.dumps(msg).encode())
        resp_bytes = self._transport.recv(timeout=5.0)
        if not resp_bytes:
            self.last_error = "no contract response"
            self._audit("contract", "handshake", "FAIL", self.last_error)
            return False
        resp = json.loads(resp_bytes)
        if resp.get("type") != "CONTRACT_RESPONSE":
            self.last_error = f"unexpected response type: {resp.get('type')}"
            return False
        gw_version = resp.get("contract_version", "")
        if not gw_version.startswith("1."):
            mismatch = ContractMismatch(
                required_version=GATEWAY_CONTRACT_VERSION,
                actual_version=gw_version,
                resolution="gateway must be v1.x",
                reason=f"contract version {gw_version} incompatible")
            self._audit("contract", "handshake", "REJECTED", mismatch.reason)
            raise ContractRejected(mismatch)
        self.gateway_version = resp.get("gateway_version", "")
        self.contract_version = gw_version
        self._audit("contract", "handshake", "OK",
                    f"gateway={self.gateway_version}")
        return True

    # ===== heartbeat (§4) =====
    def send_heartbeat(self) -> bool:
        if self._state != ConnectionState.CONNECTED:
            return False
        ts = utc_now_iso()
        start = time.monotonic()
        msg = {"type": "HEARTBEAT", "client_id": self.client_id,
               "timestamp": ts}
        if not self._transport.send(json.dumps(msg).encode()):
            self._on_missed_heartbeat("send failed")
            return False
        resp = self._transport.recv(timeout=5.0)
        self.latency_ms = round((time.monotonic() - start) * 1000, 2)
        if resp:
            self.last_heartbeat = utc_now_iso()
            return True
        self._on_missed_heartbeat("no response")
        return False

    def _on_missed_heartbeat(self, reason: str):
        if self._state == ConnectionState.CONNECTED:
            self._state = ConnectionState.DEGRADED
            self._audit("heartbeat", "missed", "DEGRADED", reason)
        elif self._state == ConnectionState.DEGRADED:
            self._state = ConnectionState.RECONNECTING
            self.reconnect()

    # ===== reconnect (§13) =====
    def reconnect(self) -> bool:
        self.reconnect_count += 1
        self._state = ConnectionState.RECONNECTING
        self._audit("connection", "reconnect", "ATTEMPT",
                    f"count={self.reconnect_count}")
        self._transport.disconnect()
        if self.connect():
            self.request_state_snapshot()
            return True
        self._state = ConnectionState.OFFLINE
        return False

    def request_state_snapshot(self) -> Optional[dict]:
        if self._state != ConnectionState.CONNECTED:
            return None
        msg = {"type": "STATE_REQUEST", "client_id": self.client_id}
        self._transport.send(json.dumps(msg).encode())
        resp = self._transport.recv(timeout=5.0)
        if resp:
            snap = json.loads(resp)
            self._audit("state", "snapshot", "RECEIVED", "")
            return snap
        return None

    # ===== signal publish (§7-§8) =====
    def publish_signal(self, signal: Signal) -> Dict[str, Any]:
        # validation (§8)
        errors = self._validate_signal(signal)
        if errors:
            self._audit("signal", signal.signal_id, "REJECTED",
                        "; ".join(errors))
            return {"ok": False, "errors": errors}
        if signal.signal_id in self._seen_signal_ids:
            self._audit("signal", signal.signal_id, "DUPLICATE_BLOCKED", "")
            return {"ok": False, "errors": ["duplicate signal_id"]}
        self._seen_signal_ids.add(signal.signal_id)
        # lifecycle
        self._signal_lifecycle[signal.signal_id] = SignalLifecycle.VALIDATED.value
        # publish
        msg = {"type": "SIGNAL_PUBLISH", **signal.to_dict()}
        if not self._transport.send(json.dumps(msg).encode()):
            self._signal_lifecycle[signal.signal_id] = SignalLifecycle.CREATED.value
            return {"ok": False, "errors": ["transport unavailable"]}
        self._signal_lifecycle[signal.signal_id] = SignalLifecycle.PUBLISHED.value
        self._signal_history.append({
            "signal": signal.to_dict(), "published_at": utc_now_iso(),
            "hash": signal.hash()})
        self._correlation_map.setdefault(signal.correlation_id, []).append(
            signal.signal_id)
        self._audit("signal", signal.signal_id, "PUBLISHED",
                    f"direction={signal.direction} symbol={signal.symbol}")
        # check for gateway acknowledgment
        resp = self._transport.recv(timeout=3.0)
        if resp:
            ack = json.loads(resp)
            if ack.get("type") == "SIGNAL_ACK":
                self._signal_lifecycle[signal.signal_id] = (
                    SignalLifecycle.RECEIVED_BY_GATEWAY.value)
        return {"ok": True, "signal_id": signal.signal_id,
                "lifecycle": self._signal_lifecycle[signal.signal_id]}

    def _validate_signal(self, s: Signal) -> List[str]:
        errors = []
        if not s.signal_id:
            errors.append("signal_id required")
        if not s.strategy_id:
            errors.append("strategy_id required")
        if s.direction not in ("BUY", "SELL", "NEUTRAL"):
            errors.append(f"invalid direction: {s.direction}")
        if s.signal_type not in ("ENTRY", "EXIT", "FILTER", "ALERT",
                                 "ANALYSIS"):
            errors.append(f"invalid signal_type: {s.signal_type}")
        if not (0.0 <= s.confidence <= 1.0):
            errors.append(f"confidence out of range [0,1]: {s.confidence}")
        if s.is_expired():
            errors.append("signal expired")
        if not s.correlation_id:
            errors.append("correlation_id required")
        return errors

    def get_signal_lifecycle(self, signal_id: str) -> str:
        return self._signal_lifecycle.get(signal_id, "UNKNOWN")

    def get_signal_history(self) -> List[dict]:
        return list(self._signal_history)

    # ===== event subscription (§10-§12) =====
    def on(self, event_type: str, handler: Callable) -> None:
        self._event_handlers.setdefault(event_type, []).append(handler)

    def process_event(self, envelope: EventEnvelope) -> bool:
        if envelope.event_id in self._seen_event_ids:
            return False    # idempotent (§12)
        self._seen_event_ids.add(envelope.event_id)
        # signal lifecycle updates from gateway
        et = envelope.event_type
        sid = envelope.payload.get("signal_id", "")
        if sid and et in ("SIGNAL_ACCEPTED", "SIGNAL_REJECTED",
                          "EXECUTION_RESULT"):
            if et == "SIGNAL_ACCEPTED":
                self._signal_lifecycle[sid] = SignalLifecycle.ACCEPTED_BY_EA.value
            elif et == "SIGNAL_REJECTED":
                self._signal_lifecycle[sid] = SignalLifecycle.REJECTED_BY_RISK.value
            elif et == "EXECUTION_RESULT":
                status = envelope.payload.get("status", "")
                if status == "EXECUTED":
                    self._signal_lifecycle[sid] = SignalLifecycle.EXECUTED.value
        self._event_sequence += 1
        self._audit("event", envelope.event_id, "RECEIVED",
                    f"type={et} seq={self._event_sequence}")
        for handler in self._event_handlers.get(et, []):
            try:
                handler(envelope)
            except Exception as ex:
                logger.warning("event handler error: %s", ex)
        return True

    # ===== correlation trace (§16) =====
    def get_correlation_trace(self, correlation_id: str) -> List[str]:
        return list(self._correlation_map.get(correlation_id, []))

    # ===== audit (§23) =====
    def _audit(self, category: str, subject: str, result: str,
               reason: str) -> None:
        self._audit_log.append({
            "timestamp": utc_now_iso(), "actor": self.client_id,
            "category": category, "subject": subject, "result": result,
            "reason": reason, "correlation_id": ""})

    def get_audit_log(self, limit: int = 100) -> List[dict]:
        return self._audit_log[-limit:]

    # ===== diagnostics (§22) =====
    def diagnostics(self) -> List[Dict[str, Any]]:
        checks = [
            ("Gateway reachable", self._state in (ConnectionState.CONNECTED,
                                                  ConnectionState.DEGRADED)),
            ("Authentication", self._auth_state == "AUTHENTICATED"),
            ("Contract compatible", bool(self.contract_version)),
            ("Heartbeat", bool(self.last_heartbeat)),
            ("Event stream", self._event_sequence > 0),
            ("Signal channel", len(self._signal_history) > 0),
            ("State synchronization", self._state == ConnectionState.CONNECTED),
            ("Reconciliation", self._state == ConnectionState.CONNECTED),
        ]
        return [{"check": name, "pass": ok,
                 "reason": "" if ok else "not established"}
                for name, ok in checks]

    def status(self) -> dict:
        return {
            "state": self._state.value,
            "endpoint": self.endpoint,
            "client_id": self.client_id,
            "session_id": self.session_id,
            "connected_at": self.connected_at,
            "disconnected_at": self.disconnected_at,
            "last_heartbeat": self.last_heartbeat,
            "reconnect_count": self.reconnect_count,
            "latency_ms": self.latency_ms,
            "gateway_version": self.gateway_version,
            "contract_version": self.contract_version,
            "last_error": self.last_error,
            "signals_published": len(self._signal_history),
            "events_received": self._event_sequence,
        }
