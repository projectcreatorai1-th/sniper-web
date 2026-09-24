"""OUR EA runtime API adapter (P2/P3).

Pattern (master command §12):  API -> RuntimeService -> OUR EA runtime.
All GET endpoints are read-only snapshots from the runtime service
(single source of truth). The two POST command endpoints go through the
service's explicit runtime command interface (operator identity
required); there are NO trading/order endpoints in P0-P3, and LIVE is
refused by the service itself.

Registered from web/backend/app.py via a single dispatch hook.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Tuple

from core.our_ea.runtime_service import get_runtime_service
from core.our_ea.ops import ModeTransitionError

ROUTES = {
    "GET /api/our_ea/health", "GET /api/our_ea/status",
    "GET /api/our_ea/runtime", "GET /api/our_ea/state",
    "GET /api/our_ea/risk", "GET /api/our_ea/events",
    "GET /api/our_ea/reconciliation", "GET /api/our_ea/manifest",
    "POST /api/our_ea/command/start_observation",
    "POST /api/our_ea/command/promote_shadow",
    "POST /api/our_ea/command/promote_demo",
    "POST /api/our_ea/command/kill",
    "POST /api/our_ea/command/live",        # always refused — audit probe
}


def _ok(payload) -> Tuple[int, list, bytes]:
    body = json.dumps({"ok": True, "data": _serial(payload)},
                      ensure_ascii=False).encode("utf-8")
    return 200, [("Content-Type", "application/json; charset=utf-8")], body


def _err(status: int, code: str, detail: str) -> Tuple[int, list, bytes]:
    body = json.dumps({"ok": False,
                       "error": {"code": code, "message": detail}},
                      ensure_ascii=False).encode("utf-8")
    return status, [("Content-Type", "application/json; charset=utf-8")], body


def _serial(x):
    if hasattr(x, "__dataclass_fields__"):
        return asdict(x)
    if isinstance(x, dict):
        return {k: _serial(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_serial(v) for v in x]
    return x


def handles(method: str, path: str) -> bool:
    return f"{method} {path}" in ROUTES


def dispatch(method: str, path: str, body: bytes,
             server_pid: int = 0) -> Tuple[int, list, bytes]:
    svc = get_runtime_service()
    if method == "GET":
        if path == "/api/our_ea/health":
            return _ok(svc.health(server_pid=server_pid))
        if path == "/api/our_ea/status":
            return _ok(svc.status())
        if path == "/api/our_ea/runtime":
            st = svc.status()
            return _ok({"runtime_version": st.provenance.runtime_version,
                        "started_at": svc.started_at,
                        "session_id": svc.session_id,
                        "mode": st.mode, "lifecycle": st.lifecycle,
                        "mt5": st.mt5_connection,
                        "evidence_model_version": st.evidence_model_version,
                        "evidence_model_hash": st.evidence_model_hash,
                        "provenance": st.provenance})
        if path == "/api/our_ea/state":
            return _ok(svc.state())
        if path == "/api/our_ea/risk":
            return _ok(svc.risk_status())
        if path == "/api/our_ea/events":
            return _ok(svc.events(limit=100))
        if path == "/api/our_ea/reconciliation":
            return _ok(svc.reconciliation())
        if path == "/api/our_ea/manifest":
            return _ok(svc.manifest())
    if method == "POST":
        try:
            req = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return _err(400, "BAD_JSON", "request body must be JSON")
        operator = str(req.get("operator", ""))
        try:
            if path.endswith("/command/start_observation"):
                return _ok(svc.command_start_observation(operator))
            if path.endswith("/command/promote_shadow"):
                return _ok(svc.command_promote_shadow(operator))
            if path.endswith("/command/promote_demo"):
                return _ok(svc.command_promote_demo(operator))
            if path.endswith("/command/kill"):
                layer = str(req.get("layer", "GLOBAL_EMERGENCY_KILL"))
                reason = str(req.get("reason", "operator kill via API"))
                return _ok(svc.command_kill(operator, layer, reason))
            if path.endswith("/command/live"):
                return _ok(svc.command_live(operator))
        except ValueError as ex:
            return _err(400, "OPERATOR_REQUIRED", str(ex))
        except ModeTransitionError as ex:
            return _err(409, "MODE_TRANSITION_REFUSED", str(ex))
    return _err(404, "NOT_FOUND", f"{method} {path}")
