"""Entry point: start the local/production web server.

Configuration via environment variables (no hard-coded deployment values):
  WEB_HOST           bind address   (default 127.0.0.1 for local development)
  WEB_PORT           port           (default 8765)
  WEB_MAX_UPLOAD_MB  upload limit   (default 8)

Standard library only - a threaded WSGI server built on wsgiref. For heavy
production traffic use any WSGI server (see DEPLOYMENT.md), e.g. waitress:
  waitress-serve --host=0.0.0.0 --port=$PORT web.backend.app:application
"""
from __future__ import annotations

import os
import sys
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

# make the project root importable no matter where this is launched from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.app import application  # noqa: E402


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_server.pid")


def main() -> None:
    # Precedence: explicit WEB_HOST/WEB_PORT env, then the PORT variable that
    # PaaS platforms (Render/Koyeb/...) inject (which also implies a 0.0.0.0
    # bind), then the local-development default 127.0.0.1:8765.
    port_env = os.environ.get("WEB_PORT") or os.environ.get("PORT")
    port = int(port_env) if port_env else 8765
    host = os.environ.get("WEB_HOST") or ("0.0.0.0" if port_env else "127.0.0.1")
    httpd = make_server(host, port, application, server_class=ThreadingWSGIServer)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    print("=" * 62)
    print("  SNIPER CashFlow — Web (EA V1.68 Simulation Model)")
    print("  Core: core/ (single source of truth) — no formulas duplicated")
    print("=" * 62)
    print(f"  Open:  http://{host}:{port}")
    print(f"  API:   http://{host}:{port}/api/health")
    print("  Press Ctrl+C to stop.")
    print("=" * 62)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


if __name__ == "__main__":
    main()
