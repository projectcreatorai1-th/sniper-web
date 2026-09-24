"""OUR EA Runtime Service (P3) — the single owner of the OUR EA runtime
lifecycle inside the unified application.

Architecture (P0-P3 master command §8):
    UI -> API -> RuntimeService -> OUR EA components

The service owns: lifecycle/mode, state snapshot, event-ledger access,
risk status, reconciliation status, health, runtime metadata, provenance
for every response. It NEVER imports Analyzer runtime
(core.calculations / core.forensics / core.evidence / core.cycle /
core.basket are forbidden imports — enforced by
tests/our_ea/test_hardening_boundary.py).

No trading command endpoints exist in P0-P3. MT5 remains NOT_CONNECTED
(ENVIRONMENT-BLOCKED until P4, which is a separate work order). LIVE is
unreachable (ModeController refuses).

Every contract response carries provenance: runtime_version,
state_version, manifest_hash, trace_id, timestamp_utc (+ session_id
where applicable).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.our_ea import MODEL_ID
from core.our_ea.contract import contract_version, load_contract
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.ops import ModeController, KillSwitchBoard, reconcile
from core.our_ea.risk_guard import RiskGuard, RiskLimits
from core.our_ea.events import EventLog, Event

RUNTIME_VERSION = "OUR-EA-RUNTIME-1.0"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _manifest() -> dict:
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    try:
        import json
        return json.load(open(os.path.join(root, "release_manifest.json"),
                              encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _manifest_hash() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    import hashlib
    try:
        return hashlib.sha256(open(os.path.join(
            root, "release_manifest.json"), "rb").read()).hexdigest().upper()
    except OSError:
        return "NOT_FOUND"


# ------------------------------------------------------------- typed contract
@dataclass(frozen=True)
class Provenance:
    runtime_version: str
    state_version: int
    manifest_hash: str
    trace_id: str
    timestamp_utc: str
    session_id: str = ""


@dataclass(frozen=True)
class RuntimeStatus:
    provenance: Provenance
    mode: str                      # INIT/OBSERVATION/SHADOW/DEMO
    lifecycle: str                 # RUNNING / SAFE / LOCKED ...
    mt5_connection: str            # NOT_CONNECTED (P0-P3 truth)
    evidence_model_version: str
    evidence_model_hash: str
    release_status: str
    live_lock: str


@dataclass(frozen=True)
class RuntimeState:
    provenance: Provenance
    state_machine: str
    cycle_sequence: int
    basket_open_positions: int
    basket_total_lots: float
    kill_switch_engaged: bool
    mode: str


@dataclass(frozen=True)
class RiskStatus:
    provenance: Provenance
    policy_source: str             # always OUR_EA_POLICY
    limits: Dict[str, float]
    violations_recent: List[str]
    safe_state: bool


@dataclass(frozen=True)
class ReconciliationStatus:
    provenance: Provenance
    status: str                    # NOT_CONNECTED (truth) / OK / MISMATCH
    mt5_connection: str
    block_new_orders: bool
    note: str


@dataclass(frozen=True)
class RuntimeEventView:
    provenance: Provenance
    total_events: int
    latest: List[dict]


@dataclass(frozen=True)
class RuntimeHealth:
    provenance: Provenance
    status: str
    server_pid: int
    mode: str
    reconciliation: str
    risk_state: str
    mt5_connection: str


# ------------------------------------------------------------------- service
class RuntimeService:
    """Owns the OUR EA runtime. Read-mostly in P0-P3 (no trading
    commands); hosts the components that P4 will feed."""

    def __init__(self):
        self.started_at = _utc()
        self.session_id = "RT-" + uuid.uuid4().hex[:10].upper()
        self.state_version = 0
        # evidence contract binding (hash verified at load)
        self.model = contract_version()
        self.registry = RuleRegistry.from_contract()
        self.mode = ModeController()
        self.kill_board = KillSwitchBoard()
        self.risk = RiskGuard(RiskLimits())
        self.event_log = EventLog(self.model.model_id)
        self.reconciliation_note = (
            "no MT5 adapter in P0-P3 — broker state unavailable; "
            "NOT_CONNECTED is the true state (fake CONNECTED forbidden)")
        self._bump("service-start")

    # ---- provenance ---------------------------------------------------
    def _bump(self, reason: str) -> str:
        self.state_version += 1
        return f"T{self.state_version:08d}"

    def _prov(self, trace_id: Optional[str] = None) -> Provenance:
        return Provenance(
            runtime_version=RUNTIME_VERSION,
            state_version=self.state_version,
            manifest_hash=_manifest_hash(),
            trace_id=trace_id or f"T{self.state_version:08d}",
            timestamp_utc=_utc(),
            session_id=self.session_id)

    # ---- snapshots (read-only) ----------------------------------------
    def status(self, trace_id: Optional[str] = None) -> RuntimeStatus:
        m = _manifest()
        return RuntimeStatus(
            provenance=self._prov(trace_id),
            mode=self.mode.mode,
            lifecycle="RUNNING",
            mt5_connection="NOT_CONNECTED",
            evidence_model_version=self.model.model_id,
            evidence_model_hash=self.model.model_hash,
            release_status=m.get("release_status", "unknown"),
            live_lock="LOCKED")

    def state(self, trace_id: Optional[str] = None) -> RuntimeState:
        return RuntimeState(
            provenance=self._prov(trace_id),
            state_machine=self.mode.mode,     # runtime mode machine state
            cycle_sequence=0,                 # no cycles until feed exists
            basket_open_positions=0,
            basket_total_lots=0.0,
            kill_switch_engaged=self.kill_board.any_engaged(),
            mode=self.mode.mode)

    def risk_status(self, trace_id: Optional[str] = None) -> RiskStatus:
        snap = self.risk.snapshot()
        return RiskStatus(
            provenance=self._prov(trace_id),
            policy_source="OUR_EA_POLICY",
            limits=snap["limits"],
            violations_recent=[r["reason"] for r in
                               (self.kill_board.log[-5:])],
            safe_state=not self.kill_board.any_engaged())

    def reconciliation(self,
                       trace_id: Optional[str] = None) -> ReconciliationStatus:
        return ReconciliationStatus(
            provenance=self._prov(trace_id),
            status="NOT_CONNECTED",
            mt5_connection="NOT_CONNECTED",
            block_new_orders=False,
            note=self.reconciliation_note)

    def events(self, limit: int = 50,
               trace_id: Optional[str] = None) -> RuntimeEventView:
        latest = []
        for e in self.event_log.all()[-limit:][::-1]:
            d = asdict(e)
            d.setdefault("session_id", self.session_id)
            d.setdefault("correlation_id", e.trace_id)  # explicit alias
            latest.append(d)
        return RuntimeEventView(
            provenance=self._prov(trace_id),
            total_events=len(self.event_log.all()),
            latest=latest)

    def health(self, server_pid: int = 0,
               trace_id: Optional[str] = None) -> RuntimeHealth:
        return RuntimeHealth(
            provenance=self._prov(trace_id),
            status="RUNNING",
            server_pid=server_pid or os.getpid(),
            mode=self.mode.mode,
            reconciliation="NOT_CONNECTED",
            risk_state="SAFE" if not self.kill_board.any_engaged()
            else "KILL_ENGAGED",
            mt5_connection="NOT_CONNECTED")

    def manifest(self) -> dict:
        m = _manifest()
        m["provenance"] = asdict(self._prov())
        return m

    # ---- operator commands (explicit runtime command interface) ---------
    def command_start_observation(self, operator: str) -> dict:
        self._require_operator(operator)
        self.mode.transition("OPERATOR_START", operator=operator,
                             reason="runtime command")
        tid = self._bump("mode")
        self.event_log.emit(event_type="STATE_TRANSITION",
                            reason=f"mode -> {self.mode.mode}",
                            execution_mode=self.mode.mode,
                            trace_id=tid,
                            session_id=self.session_id,
                            correlation_id=tid)
        return {"ok": True, "mode": self.mode.mode, "trace_id": tid}

    def command_promote_shadow(self, operator: str) -> dict:
        self._require_operator(operator)
        self.mode.transition("OPERATOR_PROMOTE_SHADOW", operator=operator,
                             reason="runtime command")
        tid = self._bump("mode")
        self.event_log.emit(event_type="STATE_TRANSITION",
                            reason=f"mode -> {self.mode.mode}",
                            execution_mode=self.mode.mode,
                            trace_id=tid,
                            session_id=self.session_id,
                            correlation_id=tid)
        return {"ok": True, "mode": self.mode.mode, "trace_id": tid}

    def command_promote_demo(self, operator: str) -> dict:
        """Demo mode requires a broker environment that does not exist in
        P0-P3 -> refused as ENVIRONMENT-BLOCKED (no fake DEMO)."""
        self._require_operator(operator)
        self.event_log.emit(
            event_type="MODEL_UNCERTAINTY",
            rule_id="MT5_ADAPTER",
            reason="DEMO promotion refused: no MT5 environment in P0-P3",
            execution_mode=self.mode.mode,
            trace_id=f"T{self.state_version:08d}",
            session_id=self.session_id,
            correlation_id=f"T{self.state_version:08d}")
        return {"ok": False, "error": "ENVIRONMENT-BLOCKED",
                "reason": "MT5 adapter/connection does not exist in P0-P3; "
                          "DEMO promotion is a P4 operation"}

    def command_kill(self, operator: str, layer: str = "GLOBAL_EMERGENCY_KILL",
                     reason: str = "operator kill") -> dict:
        self._require_operator(operator)
        rec = self.kill_board.engage(layer, reason)
        self._bump("kill")
        self.event_log.emit(event_type="SAFE_STOP",
                            reason=f"kill switch {layer}",
                            execution_mode=self.mode.mode,
                            trace_id=f"T{self.state_version:08d}",
                            session_id=self.session_id,
                            correlation_id=f"T{self.state_version:08d}")
        return {"ok": True, "kill": rec}

    def command_live(self, operator: str) -> dict:
        self._require_operator(operator)
        try:
            self.mode.request_live()
        except Exception as ex:
            self.event_log.emit(event_type="LIVE_EXECUTION_REQUESTED",
                                reason=str(ex),
                                execution_mode=self.mode.mode,
                                trace_id=f"T{self.state_version:08d}",
                                session_id=self.session_id,
                                correlation_id=f"T{self.state_version:08d}")
            return {"ok": False, "error": "LIVE_LOCKED", "detail": str(ex)}
        return {"ok": False, "error": "LIVE_LOCKED"}

    @staticmethod
    def _require_operator(operator: str) -> None:
        if not operator or not operator.strip():
            raise ValueError("operator identity required for every "
                             "runtime command")


# module-level singleton owned by the application (lazy)
_SERVICE: Optional[RuntimeService] = None


def get_runtime_service() -> RuntimeService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RuntimeService()
    return _SERVICE
