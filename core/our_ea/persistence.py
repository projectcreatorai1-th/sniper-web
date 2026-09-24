"""Persistence (§23) + recovery (§24).

Persistent state: model_version, cycle identity, state, positions,
levels, lot progression, pending actions, last event, risk state,
config version. Restore after process restart is supported, labelled
OUR_EA_RECOVERY_POLICY — never claimed as V1.68 verified restart
recovery (R-RESTART-RECOVERY = UNKNOWN).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from core.our_ea.basket import Basket, PositionRef

STATE_SCHEMA = "OUR_EA_PERSISTENCE_V1"


class PersistenceError(RuntimeError):
    pass


@dataclass
class PersistedState:
    model_version: str
    model_hash: str
    config_version: str
    execution_mode: str
    account: str
    symbol: str
    state: str
    cycle_sequence: int
    cycle_id: str
    opened_at: str
    positions: List[dict] = field(default_factory=list)
    closed_positions: List[dict] = field(default_factory=list)
    pending_actions: List[dict] = field(default_factory=list)
    last_event_id: str = ""
    last_event_ts: str = ""
    risk_state: dict = field(default_factory=dict)
    tick_no: int = 0
    idem_keys: List[list] = field(default_factory=list)
    realized_gross: float = 0.0
    uncertainties: int = 0
    schema: str = STATE_SCHEMA

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False,
                          sort_keys=True, indent=1)

    def checksum(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def snapshot(model_version: str, model_hash: str, config_version: str,
             execution_mode: str, state_machine_state: str, basket: Basket,
             cycle_sequence: int, last_event_id: str = "",
             last_event_ts: str = "", risk_state: Optional[dict] = None,
             pending_actions: Optional[List[dict]] = None,
             account: str = "SIM", symbol: str = "GOLDmicro",
             tick_no: int = 0, idem_keys: Optional[List[list]] = None,
             realized_gross: float = 0.0, uncertainties: int = 0) -> PersistedState:
    return PersistedState(
        model_version=model_version, model_hash=model_hash,
        config_version=config_version, execution_mode=execution_mode,
        account=account, symbol=symbol, state=state_machine_state,
        cycle_sequence=cycle_sequence, cycle_id=basket.cycle_id,
        opened_at=basket.opened_at,
        positions=[asdict(p) for p in basket.positions],
        closed_positions=[asdict(p) for p in basket.closed_positions],
        pending_actions=list(pending_actions or []),
        last_event_id=last_event_id, last_event_ts=last_event_ts,
        risk_state=dict(risk_state or {}), tick_no=tick_no,
        idem_keys=[list(k) for k in (idem_keys or [])],
        realized_gross=realized_gross, uncertainties=uncertainties)


class StateCorruptionError(PersistenceError):
    """Checksum/schema mismatch — partial state must NOT be accepted."""


class StateStore:
    """Atomic JSON persistence with checksum integrity.

    save(): temp file + fsync + checksum envelope + atomic replace.
    load(): verifies envelope checksum and schema; any mismatch raises
    StateCorruptionError -> caller must SAFE STOP (never best-effort
    recovery). This is OUR EA safety behavior, not verified V1.68
    behavior."""

    def __init__(self, path: str):
        self.path = path

    def save(self, st: PersistedState) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        envelope = {"state": json.loads(st.to_json()),
                    "checksum": st.checksum()}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def load(self, expected_model: Optional[tuple] = None) -> PersistedState:
        if not os.path.exists(self.path):
            raise PersistenceError(f"no persisted state at {self.path}")
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
        except json.JSONDecodeError as ex:
            raise StateCorruptionError(f"unparseable state: {ex}") from ex
        state_doc = envelope.get("state") if isinstance(envelope, dict) else None
        checksum = envelope.get("checksum") if isinstance(envelope, dict) else None
        if not isinstance(state_doc, dict) or not checksum:
            raise StateCorruptionError("missing state envelope/checksum")
        try:
            probe = PersistedState(**{k: v for k, v in state_doc.items()
                                      if k in PersistedState.__dataclass_fields__})
        except TypeError as ex:
            raise StateCorruptionError(
                f"missing/invalid required fields: {ex}") from ex
        if probe.schema != STATE_SCHEMA:
            raise StateCorruptionError(f"unknown schema: {probe.schema}")
        if hashlib.sha256(probe.to_json().encode("utf-8")).hexdigest() != checksum:
            raise StateCorruptionError("state checksum mismatch (corrupted)")
        if expected_model is not None:
            exp_id, exp_hash = expected_model
            if (probe.model_version, probe.model_hash) != (exp_id, exp_hash):
                raise PersistenceError(
                    f"MODEL_VERSION_MISMATCH on restore: state has "
                    f"{probe.model_version}@{probe.model_hash[:10]}… expected "
                    f"{exp_id}@{exp_hash[:10]}…")
        return probe

    def restore_basket(self, st: PersistedState) -> Basket:
        b = Basket(st.cycle_id, st.opened_at)
        b.positions = [PositionRef(**p) for p in st.positions]
        b.closed_positions = [PositionRef(**p) for p in st.closed_positions]
        return b


# --------------------------------------------------------------------- §24
class RecoveryPolicy:
    """OUR_EA_POLICY — not V1.68 verified behaviour.

    On disconnect/restart with an open basket we choose the SAFE action:
    enter RECOVERY, refuse new grid adds, evaluate basket close only
    through the configured hypothesis, and require operator confirmation
    for anything the evidence cannot decide (uncertainty rules)."""

    SOURCE = "OUR_EA_POLICY"
    RULE_NOTE = "R-RESTART-RECOVERY=UNKNOWN -> MODEL_UNCERTAINTY"

    def on_reconnect_with_open_basket(self) -> dict:
        return {"action": "ADOPT_STATE",
                "adopt_positions": True,
                "allow_new_cycles": False,
                "allow_grid_adds": False,
                "allow_basket_close": True,
                "require_uncertainty_ack": True,
                "source": self.SOURCE,
                "reason": self.RULE_NOTE}

    def on_state_corrupt(self) -> dict:
        return {"action": "SAFE_STOP",
                "source": self.SOURCE,
                "reason": "persisted state unreadable/corrupt -> stop safely"}

    STALE_STATE_THRESHOLD_S = 24 * 3600

    def on_stale_state(self, age_s: float) -> dict:
        if age_s > self.STALE_STATE_THRESHOLD_S:
            return {"action": "SAFE_STOP", "source": self.SOURCE,
                    "reason": "state older than threshold — market gap "
                              "unknowable, state cannot be trusted"}
        return {"action": "ADOPT_STATE", "source": self.SOURCE,
                "reason": "state fresh enough to adopt"}

    def on_missing_state_with_positions(self) -> dict:
        return {"action": "PAUSE_FOR_OPERATOR",
                "source": self.SOURCE,
                "reason": "broker positions exist but no state file — "
                          "cannot attribute to a cycle (V1.68 restart "
                          "behaviour UNKNOWN)"}
