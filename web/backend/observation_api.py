"""Observation-session API handlers (Phase 2) - real functionality only.

All logic lives in core (observation/comparators/report); this module only
parses requests, calls core, and serializes results.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from core.behavior_comparators import run_all_comparators
from core.behavior_report import build_behavior_report
from core.config import EAConfig
from core.cycle import build_cycle_timelines
from core.model_rules import ModelVersionStore
from core.observation import (
    CONTROLLED_TEST_PLANS,
    OBSERVATION_SOURCES,
    ObservationSession,
    ObservationSessionStore,
    import_file,
)
from core.symbol_profile import SymbolProfile, builtin_profiles
from web.backend.parsers import RequestError, parse_multipart, read_json_body

IMPORT_EXTENSIONS = (".csv", ".txt", ".log", ".htm", ".html")

_STORE: Optional[ObservationSessionStore] = None


def _store() -> ObservationSessionStore:
    global _STORE
    if _STORE is None:
        _STORE = ObservationSessionStore()
    return _STORE


def _load(sid: str) -> ObservationSession:
    try:
        return _store().load(sid)
    except KeyError:
        raise RequestError(f"observation session not found: {sid}",
                           code="NOT_FOUND") from None


# ---------------------------------------------------------------------------
def create_session(body: dict) -> dict:
    body = body or {}
    allowed = {"ea_version", "environment_profile_id", "symbol", "timeframe",
               "broker", "account_type", "initial_balance", "start_time",
               "end_time", "parameters", "source_type", "source_reference",
               "notes"}
    unknown = [k for k in body if k not in allowed]
    if unknown:
        raise RequestError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    params = body.get("parameters")
    if params is not None:
        if not isinstance(params, dict):
            raise RequestError("'parameters' must be an object (EAConfig dict)")
        EAConfig.from_dict(params)  # validate through the core model
    try:
        session = ObservationSession.new(**body)
    except ValueError as exc:
        raise RequestError(str(exc))
    _store().save(session)
    return {"session": {k: v for k, v in session.to_dict().items() if k != "events"},
            "event_count": 0,
            "source_types": list(OBSERVATION_SOURCES)}


def import_into_session(sid: str, raw_body: bytes, content_type: str,
                        max_bytes: int) -> dict:
    session = _load(sid)
    if "multipart/form-data" not in content_type:
        raise RequestError("Content-Type must be multipart/form-data with a 'file' field")
    fields = parse_multipart(raw_body, content_type)
    if "file" not in fields:
        raise RequestError("multipart field 'file' is required")
    raw_filename, content = fields["file"]
    if len(content) > max_bytes:
        raise RequestError(f"Upload too large (> {max_bytes} bytes)", "PAYLOAD_TOO_LARGE")

    name = os.path.basename((raw_filename or "").strip().replace("\\", "_").replace("/", "_"))
    lowered = name.lower()
    ext = os.path.splitext(lowered)[1]
    if ext not in IMPORT_EXTENSIONS:
        raise RequestError(
            f"Unsupported file type - allowed: {', '.join(IMPORT_EXTENSIONS)}",
            "UNSUPPORTED_FILE_TYPE")
    kind_raw = (fields.get("source_kind", (b"", b""))[0] or b"").decode("utf-8", "replace").strip()
    if not kind_raw:
        kind_raw = {".csv": "MT5_CSV", ".htm": "MT5_TESTER", ".html": "MT5_TESTER",
                    ".txt": "MT5_JOURNAL", ".log": "MT5_JOURNAL"}[ext]
    mapping = None
    map_raw = (fields.get("mapping", (b"", b""))[0] or b"").decode("utf-8", "replace").strip()
    if map_raw:
        try:
            mapping = json.loads(map_raw)
        except json.JSONDecodeError:
            raise RequestError("'mapping' must be a JSON object {field: column}")

    import tempfile
    tmp = tempfile.NamedTemporaryFile(prefix="sniper_obs_", suffix=ext, delete=False)
    try:
        tmp.write(content)
        tmp.close()
        records, result = import_file(tmp.name, kind_raw, mapping)
    except (ValueError, OSError) as exc:
        raise RequestError(f"import failed: {exc}")
    finally:
        os.unlink(tmp.name)

    if result.rows_imported == 0:
        raise RequestError(
            "import produced 0 events (" + "; ".join(result.warnings[:3]) +
            ") - nothing was saved", code="EMPTY_IMPORT")
    session.events = session.events + records
    session.source_type = kind_raw
    session.source_reference = session.source_reference or name
    if not session.symbol and records and records[0].symbol:
        session.symbol = records[0].symbol
    _store().save(session)
    return {"session_id": sid, "import_result": result.to_dict(),
            "event_count": len(session.events),
            "event_summary": session.event_summary()}


def get_session(sid: str) -> dict:
    session = _load(sid)
    d = session.to_dict()
    d.pop("events", None)
    return {"session": d, "event_count": len(session.events),
            "event_summary": session.event_summary()}


def get_events(sid: str) -> dict:
    session = _load(sid)
    return {"session_id": sid, "count": len(session.events),
            "events": [e.to_dict() for e in session.events]}


def _profile_for(session: ObservationSession) -> SymbolProfile:
    for p in builtin_profiles():
        if p.name == session.symbol:
            return p
    return SymbolProfile()


def get_comparison(sid: str) -> dict:
    session = _load(sid)
    config = EAConfig.from_dict(session.parameters or EAConfig().to_dict())
    return run_all_comparators(session.events, config, _profile_for(session),
                               ModelVersionStore().active_rules(),
                               evidence_ids=[f"session:{sid}"])


def get_timeline(sid: str) -> dict:
    session = _load(sid)
    timelines = build_cycle_timelines(session.events)
    return {"session_id": sid,
            "cycle_count": len(timelines),
            "complete": sum(1 for t in timelines if t["status"] == "COMPLETE"),
            "incomplete": sum(1 for t in timelines if t["status"] == "INCOMPLETE"),
            "timelines": timelines}


def get_report(sid: str) -> dict:
    session = _load(sid)
    return build_behavior_report(session, _profile_for(session))


def get_test_plans() -> dict:
    return {"test_plans": CONTROLLED_TEST_PLANS}
