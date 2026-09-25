"""Gateway API endpoints — read-only status + signal history + audit."""
from __future__ import annotations

import json
from typing import Tuple

from core.gateway.client import GatewayClient, LoopbackTransport
from core.gateway.contracts import ConnectionState

_client: GatewayClient = GatewayClient(transport=LoopbackTransport(),
                                       endpoint="test://loopback")


def get_client() -> GatewayClient:
    return _client


ROUTES = {
    "GET /api/gateway/status", "GET /api/gateway/signals",
    "GET /api/gateway/audit", "GET /api/gateway/diagnostics",
    "POST /api/gateway/connect", "POST /api/gateway/disconnect",
    "POST /api/gateway/heartbeat",
}


def handles(method: str, path: str) -> bool:
    return f"{method} {path}" in ROUTES


def _ok(payload) -> Tuple[int, list, bytes]:
    body = json.dumps({"ok": True, "data": payload},
                      ensure_ascii=False, default=str).encode("utf-8")
    return 200, [("Content-Type", "application/json; charset=utf-8")], body


def _err(status: int, code: str, msg: str) -> Tuple[int, list, bytes]:
    body = json.dumps({"ok": False,
                       "error": {"code": code, "message": msg}},
                      ensure_ascii=False).encode("utf-8")
    return status, [("Content-Type", "application/json; charset=utf-8")], body


def dispatch(method: str, path: str, body: bytes) -> Tuple[int, list, bytes]:
    c = get_client()
    if method == "GET":
        if path == "/api/gateway/status":
            return _ok(c.status())
        if path == "/api/gateway/signals":
            return _ok({"signals": c.get_signal_history(),
                        "lifecycle": {k: v for k, v in
                                      c._signal_lifecycle.items()}})
        if path == "/api/gateway/audit":
            return _ok({"audit": c.get_audit_log(200)})
        if path == "/api/gateway/diagnostics":
            return _ok({"diagnostics": c.diagnostics()})
    if method == "POST":
        if path == "/api/gateway/connect":
            if c.connect():
                return _ok({"state": c.get_state().value})
            return _err(503, "CONNECT_FAILED", c.last_error)
        if path == "/api/gateway/disconnect":
            c.disconnect()
            return _ok({"state": c.get_state().value})
        if path == "/api/gateway/heartbeat":
            if c.send_heartbeat():
                return _ok({"latency_ms": c.latency_ms})
            return _err(503, "HEARTBEAT_FAILED", "not connected")
    return _err(404, "NOT_FOUND", f"{method} {path}")
