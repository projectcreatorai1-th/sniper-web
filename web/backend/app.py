"""WSGI application for the SNIPER CashFlow web version.

Standard-library only (matches the project's zero-dependency policy).
Routing + static file serving + error handling live here; the actual API
logic is in web/backend/api.py and every calculation in core/*.

Run locally:  python web/backend/run_server.py   (or start_web.bat)
Production:   any WSGI server, e.g.
              waitress-serve --host=0.0.0.0 --port=$PORT web.backend.app:application
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Callable, Dict, List, Tuple

from web.backend import api, observation_api
from web.backend.parsers import RequestError, read_json_body

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
MAX_JSON_BODY = 2 * 1024 * 1024


class HTTPError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


_STATUS_TEXT = {200: "OK", 400: "Bad Request", 404: "Not Found",
                405: "Method Not Allowed", 413: "Payload Too Large",
                500: "Internal Server Error"}

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


def _json_response(status: int, payload: dict) -> Tuple[int, List[Tuple[str, str]], bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
    ]
    return status, headers, body


def _error_payload(code: str, message: str, details=None) -> dict:
    err: Dict[str, object] = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"ok": False, "error": err}


def _static_response(rel_path: str) -> Tuple[int, List[Tuple[str, str]], bytes]:
    """Serve a file from web/frontend (traversal-safe, no directory listing)."""
    root = os.path.abspath(FRONTEND_DIR)
    target = os.path.abspath(os.path.join(root, rel_path))
    if not target.startswith(root + os.sep) and target != root:
        raise HTTPError(404, "Not found")
    if not os.path.isfile(target):
        raise HTTPError(404, "Not found")
    ext = os.path.splitext(target)[1].lower()
    ctype = _CONTENT_TYPES.get(ext, "application/octet-stream")
    with open(target, "rb") as f:
        body = f.read()
    headers = [
        ("Content-Type", ctype),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-cache"),
        ("X-Content-Type-Options", "nosniff"),
    ]
    return 200, headers, body


# ---------------------------------------------------------------------------
# routes: path -> callable(environ, body) returning dict | api.FileResponse
# ---------------------------------------------------------------------------
def _route_health(environ, body):
    return api.health()


def _route_config(environ, body):
    return api.get_config()


def _route_assumptions(environ, body):
    return api.get_assumptions()


def _route_evidence(environ, body):
    return api.get_evidence()


def _route_environment(environ, body):
    return api.get_environment()


def _route_parameters(environ, body):
    return api.get_parameters()


def _route_ex5_integrity(environ, body):
    return api.get_ex5_integrity()


def _route_validate(environ, body):
    return api.validate(body)


def _route_grid(environ, body):
    return api.grid_calculate(body)


def _route_worst_case(environ, body):
    return api.worst_case_simulate(body)


def _route_risk(environ, body):
    return api.risk_calculate(body)


def _route_basket(environ, body):
    return api.basket_simulate(body)


def _route_set_builder(environ, body):
    return api.set_builder_generate(body)


def _route_backtest(environ, body):
    max_upload = int(os.environ.get("WEB_MAX_UPLOAD_MB", "8")) * 1024 * 1024
    return api.backtest_analyze(environ, max_upload)


def _route_report(environ, body):
    return api.report(body)


ROUTES: Dict[str, Callable] = {
    "/api/health": _route_health,
    "/api/config": _route_config,
    "/api/assumptions": _route_assumptions,
    "/api/evidence": _route_evidence,
    "/api/environment": _route_environment,
    "/api/parameters": _route_parameters,
    "/api/ex5-integrity": _route_ex5_integrity,
    "/api/validate": _route_validate,
    "/api/grid/calculate": _route_grid,
    "/api/worst-case/simulate": _route_worst_case,
    "/api/risk/calculate": _route_risk,
    "/api/basket/simulate": _route_basket,
    "/api/set-builder/generate": _route_set_builder,
    "/api/backtest/analyze": _route_backtest,
    "/api/report": _route_report,
}


def _dispatch_observation(path: str, environ: dict) -> object:
    method = environ["REQUEST_METHOD"].upper()
    parts = [p for p in path.split("/") if p]      # api/observation-sessions[/id[/sub]]
    if len(parts) == 2:
        if method != "POST":
            raise HTTPError(405, "use POST to create an observation session")
        return observation_api.create_session(read_json_body(environ, MAX_JSON_BODY))
    if len(parts) >= 3:
        sid, sub = parts[2], (parts[3] if len(parts) > 3 else "")
        if sub == "" and method == "GET":
            return observation_api.get_session(sid)
        if sub == "events" and method == "GET":
            return observation_api.get_events(sid)
        if sub == "comparison" and method == "GET":
            return observation_api.get_comparison(sid)
        if sub == "timeline" and method == "GET":
            return observation_api.get_timeline(sid)
        if sub == "report" and method == "GET":
            return observation_api.get_report(sid)
        if sub == "import" and method == "POST":
            ctype = environ.get("CONTENT_TYPE", "")
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = 0
            max_upload = int(os.environ.get("WEB_MAX_UPLOAD_MB", "8")) * 1024 * 1024
            if length > max_upload:
                raise RequestError(f"Upload too large (> {max_upload} bytes)",
                                   "PAYLOAD_TOO_LARGE")
            raw = environ["wsgi.input"].read(length) if length else b""
            from web.backend.parsers import read_bounded
            if len(raw) < length:                    # drain remainder if any
                raw += read_bounded(environ, 0)
            return observation_api.import_into_session(sid, raw, ctype, max_upload)
        raise HTTPError(405, f"unsupported method/sub-path for observation session")
    raise HTTPError(404, "Not found")


def _dispatch_api(path: str, environ: dict):
    if path.startswith("/api/observation-sessions"):
        return _dispatch_observation(path, environ)
    if path == "/api/test-plans":
        if environ["REQUEST_METHOD"].upper() != "GET":
            raise HTTPError(405, "GET only")
        return observation_api.get_test_plans()
    handler = ROUTES[path]
    body = {}
    if environ["REQUEST_METHOD"] == "POST" and path != "/api/backtest/analyze":
        # the backtest endpoint reads its multipart body itself
        from web.backend.parsers import read_json_body
        body = read_json_body(environ, MAX_JSON_BODY)
    return handler(environ, body)


def application(environ, start_response):
    method = environ["REQUEST_METHOD"].upper()
    path = environ.get("PATH_INFO", "/") or "/"

    try:
        # ---- API -----------------------------------------------------------
        if path.startswith("/api/"):
            _param_route = (path.startswith("/api/observation-sessions")
                            or path == "/api/test-plans")
            _get_only = path in (
                "/api/health", "/api/config", "/api/assumptions",
                "/api/evidence", "/api/environment", "/api/parameters",
                "/api/ex5-integrity")
            _post_only = path in ROUTES and not _get_only
            # param-based observation routes enforce their own methods in
            # _dispatch_observation (create/import=POST, rest=GET)
            if method not in ("GET", "POST", "HEAD"):
                raise HTTPError(405, f"Method {method} not allowed")
            if method == "POST" and _get_only:
                raise HTTPError(405, f"{path} accepts GET only")
            if method == "GET" and _post_only and path != "/api/observation-sessions":
                raise HTTPError(405, f"{path} accepts POST only")
            if not _param_route and path not in ROUTES:
                raise HTTPError(404, f"Unknown API endpoint: {path}")
            result = _dispatch_api(path, environ)
            if isinstance(result, api.FileResponse):
                headers = [
                    ("Content-Type", result.content_type),
                    ("Content-Length", str(len(result.body))),
                    ("Content-Disposition",
                     f'attachment; filename="{result.filename}"'),
                    ("Cache-Control", "no-store"),
                    ("X-Content-Type-Options", "nosniff"),
                ]
                status, payload_body = 200, result.body
            else:
                status, headers, payload_body = _json_response(
                    200, {"ok": True, "data": result})
            if method == "HEAD":
                payload_body = b""

        # ---- static frontend ------------------------------------------------
        elif method in ("GET", "HEAD"):
            if path in ("/", "/index.html"):
                status, headers, payload_body = _static_response("index.html")
            elif path.startswith("/static/"):
                status, headers, payload_body = _static_response(path[len("/static/"):])
            elif os.path.splitext(path)[1]:
                # asset-like paths (e.g. /favicon.ico) do not fall back to the SPA
                raise HTTPError(404, "Not found")
            else:
                # SPA-friendly: any other GET falls back to the app shell
                status, headers, payload_body = _static_response("index.html")
            if method == "HEAD":
                payload_body = b""

        else:
            raise HTTPError(405, f"Method {method} not allowed")

    except RequestError as exc:
        status = 413 if exc.code == "PAYLOAD_TOO_LARGE" else 400
        status, headers, payload_body = _json_response(
            status, _error_payload(exc.code, str(exc), exc.details))
    except HTTPError as exc:
        status, headers, payload_body = _json_response(
            exc.status, _error_payload("HTTP_ERROR", exc.message))
    except ValueError as exc:
        # a core function rejected the input (e.g. bad numeric range)
        status, headers, payload_body = _json_response(
            400, _error_payload("VALIDATION_ERROR", str(exc)))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        status, headers, payload_body = _json_response(
            500, _error_payload("INTERNAL_ERROR", "Internal server error"))

    start_response(f"{status} {_STATUS_TEXT.get(status, 'Error')}", headers)
    return [payload_body]
