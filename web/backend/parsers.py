"""Request parsing / validation helpers for the web backend.

Contains NO calculation logic - only structural validation and coercion.
Every calculation stays in core/* (single source of truth). Unknown keys are
rejected (400) so typos surface early instead of being silently ignored.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.config import EAConfig
from core.model_rules import SimulationModelRules, ModelVersionStore
from core.risk import RiskThresholds
from core.symbol_profile import AccountSettings, SymbolProfile

from dataclasses import fields as dc_fields


class RequestError(Exception):
    """Raised for any client-input problem -> HTTP 400 with details."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR",
                 details: Optional[List[str]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or []


# ---------------------------------------------------------------------------
# body reading
# ---------------------------------------------------------------------------
def read_bounded(environ: Dict[str, Any], limit: int,
                 hard_cap: int = 64 * 1024 * 1024) -> bytes:
    """Read the request body keeping at most `limit` bytes, draining the rest
    (bounded by `hard_cap`).

    Draining matters when the body is oversized and will be rejected: if the
    server responded 413 while the client is still sending, the response can
    be lost to a connection reset. Consuming the declared body first lets the
    client always receive the error response.
    """
    stream = environ.get("wsgi.input")
    if stream is None:
        return b""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    todo: Optional[int] = length if length > 0 else None
    keep: List[bytes] = []
    kept = 0
    total = 0
    while total < hard_cap and (todo is None or todo > 0):
        want = 65536 if todo is None else min(65536, todo)
        chunk = stream.read(want)
        if not chunk:
            break
        if todo is not None:
            todo -= len(chunk)
        total += len(chunk)
        if kept < limit:
            keep.append(chunk)
            kept += len(chunk)
    return b"".join(keep)[:limit]


def read_json_body(environ: Dict[str, Any], max_bytes: int) -> dict:
    """Read and parse the request body as a JSON object."""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        raise RequestError("Invalid Content-Length")
    body = read_bounded(environ, max_bytes + 1)
    if length <= 0 and not body:
        raise RequestError("Request body required (JSON object)")
    if length > max_bytes or len(body) > max_bytes:
        raise RequestError(f"Request body too large (> {max_bytes} bytes)", "PAYLOAD_TOO_LARGE")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError(f"Body is not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise RequestError("Request body must be a JSON object")
    return data


# ---------------------------------------------------------------------------
# typed field extraction
# ---------------------------------------------------------------------------
def get_object(body: dict, key: str, default: Optional[dict] = None) -> dict:
    val = body.get(key, default)
    if val is None:
        return default if default is not None else {}
    if not isinstance(val, dict):
        raise RequestError(f"'{key}' must be an object")
    return val


def require_number(body: dict, key: str, minimum: Optional[float] = None,
                   maximum: Optional[float] = None) -> float:
    if key not in body:
        raise RequestError(f"'{key}' is required")
    return coerce_number(body[key], key, minimum, maximum)


def optional_number(body: dict, key: str, minimum: Optional[float] = None,
                    maximum: Optional[float] = None) -> Optional[float]:
    if body.get(key) is None:
        return None
    return coerce_number(body[key], key, minimum, maximum)


def coerce_number(val: Any, name: str, minimum: Optional[float] = None,
                  maximum: Optional[float] = None) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise RequestError(f"'{name}' must be a number")
    v = float(val)
    if minimum is not None and v < minimum:
        raise RequestError(f"'{name}' must be >= {minimum}")
    if maximum is not None and v > maximum:
        raise RequestError(f"'{name}' must be <= {maximum}")
    return v


def require_int(body: dict, key: str, minimum: int, maximum: int) -> int:
    if key not in body:
        raise RequestError(f"'{key}' is required")
    val = body[key]
    if isinstance(val, bool) or not isinstance(val, int):
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        else:
            raise RequestError(f"'{key}' must be an integer")
    if not (minimum <= val <= maximum):
        raise RequestError(f"'{key}' must be between {minimum} and {maximum}")
    return int(val)


def require_choice(body: dict, key: str, choices: Tuple[str, ...],
                   default: Optional[str] = None) -> str:
    val = body.get(key, default)
    if val is None:
        raise RequestError(f"'{key}' is required")
    if val not in choices:
        raise RequestError(f"'{key}' must be one of {list(choices)}")
    return val


def require_number_list(body: dict, key: str, min_len: int, max_len: int,
                        minimum: Optional[float] = None) -> List[float]:
    val = body.get(key)
    if not isinstance(val, list):
        raise RequestError(f"'{key}' must be an array of numbers")
    if not (min_len <= len(val) <= max_len):
        raise RequestError(f"'{key}' must contain {min_len}-{max_len} values")
    return [coerce_number(v, key, minimum) for v in val]


# ---------------------------------------------------------------------------
# core object builders (use core from_dict coercion, reject unknown keys)
# ---------------------------------------------------------------------------
def _reject_unknown(d: dict, allowed: set, what: str) -> None:
    unknown = [k for k in d if k not in allowed]
    if unknown:
        raise RequestError(f"Unknown {what} key(s): {', '.join(sorted(unknown))}",
                           details=[f"unknown key: {k}" for k in sorted(unknown)])


def build_config(body: dict) -> EAConfig:
    raw = get_object(body, "config")
    if not raw:
        return EAConfig()
    _reject_unknown(raw, {f.name for f in dc_fields(EAConfig)} | {"schema"}, "config")
    try:
        return EAConfig.from_dict(raw)
    except (ValueError, TypeError) as exc:
        raise RequestError(f"Invalid 'config' value: {exc}")


def build_profile(body: dict) -> SymbolProfile:
    raw = get_object(body, "symbol_profile")
    if not raw:
        return SymbolProfile()
    _reject_unknown(raw, {f.name for f in dc_fields(SymbolProfile)}, "symbol_profile")
    try:
        p = SymbolProfile.from_dict(raw)
    except (ValueError, TypeError) as exc:
        raise RequestError(f"Invalid 'symbol_profile' value: {exc}")
    if p.contract_size <= 0 or p.lot_step <= 0 or p.reference_price <= 0:
        raise RequestError("symbol_profile requires contract_size/lot_step/reference_price > 0")
    return p


def build_account(body: dict) -> AccountSettings:
    raw = get_object(body, "account")
    if not raw:
        return AccountSettings()
    _reject_unknown(raw, {f.name for f in dc_fields(AccountSettings)}, "account")
    try:
        return AccountSettings.from_dict(raw)
    except (ValueError, TypeError) as exc:
        raise RequestError(f"Invalid 'account' value: {exc}")


def build_rules(body: dict) -> SimulationModelRules:
    raw = get_object(body, "model_rules")
    if not raw:
        return ModelVersionStore().active_rules()
    _reject_unknown(raw, {f.name for f in dc_fields(SimulationModelRules)}, "model_rules")
    try:
        rules = SimulationModelRules.from_dict(raw)
    except (ValueError, TypeError) as exc:
        raise RequestError(f"Invalid 'model_rules' value: {exc}")
    errs = rules.validate()
    if errs:
        raise RequestError("; ".join(errs))
    return rules


def build_thresholds(body: dict) -> RiskThresholds:
    raw = get_object(body, "thresholds")
    if not raw:
        return RiskThresholds()
    _reject_unknown(raw, {f.name for f in dc_fields(RiskThresholds)}, "thresholds")
    try:
        t = RiskThresholds.from_dict(raw)
    except (ValueError, TypeError) as exc:
        raise RequestError(f"Invalid 'thresholds' value: {exc}")
    if t.max_simulated_grid_levels < 1 or t.max_simulated_grid_levels > 500:
        raise RequestError("thresholds.max_simulated_grid_levels must be 1-500")
    if t.reference_adverse_move_usd < 0:
        raise RequestError("thresholds.reference_adverse_move_usd must be >= 0")
    return t


# ---------------------------------------------------------------------------
# multipart/form-data parsing (for backtest upload)
# ---------------------------------------------------------------------------
_FILENAME_STRIP = re.compile(r'[\\/:*?"<>|\r\n]')


def parse_multipart(body: bytes, content_type: str) -> Dict[str, Tuple[str, bytes]]:
    """Minimal, strict multipart parser. Returns {field: (filename, bytes)}.

    Only used for the backtest upload - never executes anything.
    """
    m = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not m:
        raise RequestError("multipart/form-data with a boundary is required")
    boundary = m.group(1).encode("latin-1")
    delim = b"--" + boundary
    fields: Dict[str, Tuple[str, bytes]] = {}
    # split on delimiter; first chunk is preamble, last after closing '--'
    chunks = body.split(delim)
    for chunk in chunks[1:-1] if len(chunks) > 2 else chunks[1:]:
        if chunk in (b"--", b"--\r\n", b"", b"\r\n"):
            continue
        part = chunk
        if part.startswith(b"\r\n"):
            part = part[2:]
        elif part.startswith(b"\n"):
            part = part[1:]
        # strip trailing CRLF added before the next delimiter
        if part.endswith(b"\r\n"):
            part = part[:-2]
        elif part.endswith(b"\n"):
            part = part[:-1]
        sep = part.find(b"\r\n\r\n")
        alt = part.find(b"\n\n")
        if sep == -1 and alt == -1:
            continue
        head_end = sep if (sep != -1 and (alt == -1 or sep < alt)) else alt
        head_len = 4 if head_end == sep and sep != -1 else 2
        raw_head = part[:head_end].decode("utf-8", errors="replace")
        content = part[head_end + head_len:]
        disposition = ""
        for line in raw_head.splitlines():
            if line.lower().startswith("content-disposition:"):
                disposition = line
                break
        name_m = re.search(r'name="([^"]*)"', disposition)
        file_m = re.search(r'filename="([^"]*)"', disposition)
        if not name_m:
            continue
        fields[name_m.group(1)] = (file_m.group(1) if file_m else "", content)
    if not fields:
        raise RequestError("multipart body contains no form fields")
    return fields


def safe_upload_filename(raw_name: str, allowed_exts: Tuple[str, ...]) -> str:
    """Sanitize an uploaded filename and enforce the extension whitelist."""
    name = _FILENAME_STRIP.sub("_", (raw_name or "").strip())[:180]
    if not name:
        raise RequestError("Uploaded file must have a filename")
    lowered = name.lower()
    for ext in allowed_exts:
        if lowered.endswith(ext):
            return name
    raise RequestError(
        f"Unsupported file type - allowed extensions: {', '.join(allowed_exts)}",
        "UNSUPPORTED_FILE_TYPE")
