"""Web test helpers: in-process WSGI call, multipart builder, std body.

tests/web is intentionally NOT a package (no __init__.py) so the desktop
runner (run_tests.py) skips it; run_web_tests.py discovers it with
tests/web itself on sys.path, so helpers import as a top-level module.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from web.backend.app import application  # noqa: E402


def call_app(method, path, body=None, content_type="application/json"):
    """Call the WSGI app in-process. body: dict (JSON) or raw bytes.
    Returns (status:int, headers:dict, payload:dict-or-bytes)."""
    if isinstance(body, dict):
        raw = json.dumps(body).encode("utf-8")
    elif isinstance(body, bytes):
        raw = body
    else:
        raw = b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(raw)),
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "wsgi.input": io.BytesIO(raw),
        "wsgi.errors": io.StringIO(),
        "wsgi.url_scheme": "http",
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    chunks = application(environ, start_response)
    out = b"".join(chunks)
    ctype = captured["headers"].get("Content-Type", "")
    if "json" in ctype:
        try:
            return captured["status"], captured["headers"], json.loads(out.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return captured["status"], captured["headers"], out
    return captured["status"], captured["headers"], out


def multipart_body(filename, content, field="file", boundary="sniperTestBound42"):
    """Build a minimal valid multipart/form-data body."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + content + tail, f"multipart/form-data; boundary={boundary}"


def std_body(**extra):
    """Standard request body: default config, XAUUSD profile, 1:500 account."""
    from core.config import EAConfig
    from core.symbol_profile import AccountSettings, SymbolProfile

    body = {
        "config": EAConfig().to_dict(),
        "symbol_profile": SymbolProfile().to_dict(),
        "account": AccountSettings().to_dict(),
    }
    body.update(extra)
    return body
