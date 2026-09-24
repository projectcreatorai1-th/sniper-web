"""Entry point: the unified application server (P1 lifecycle hardening).

  * argparse --host/--port (explicit args WIN; env WEB_HOST/WEB_PORT/PORT
    still honoured for PaaS when no args are given)
  * single-instance lock: PID file + process-identity verification
    (command line must reference run_server.py) — a live matching
    instance refuses startup; a stale/foreign PID file is cleared
    safely WITHOUT terminating anything
  * port preflight: port already bound -> refuse
  * clean shutdown on SIGINT/SIGTERM: stop -> flush -> release lock ->
    remove OWN pid only (never another process's)
  * startup diagnostics: project root, pid, host/port, lock, runtime
    version, release manifest + hash, frozen evidence hash

Standard library only. For heavy production traffic use any WSGI
server (see DEPLOYMENT.md), e.g. waitress.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

# make the project root importable no matter where this is launched from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from web.backend.app import application  # noqa: E402

# PID/lock location: default beside the server; tests/deployments may
# isolate it via SNIPER_PID_FILE (lifecycle tests use a temp dir).
PID_FILE = os.environ.get("SNIPER_PID_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "web_server.pid")
LOCK_SENTINEL = "SNIPER-SERVER-LOCK-V1"


class LifecycleError(RuntimeError):
    """Startup refused by the lifecycle guard."""


# ------------------------------------------------------------------ identity
def pid_alive(pid: int) -> bool:
    """True if a process with this pid exists (no guessing about WHO)."""
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def pid_is_our_server(pid: int) -> bool:
    """Verify identity via the process command line — never kill on pid
    number alone."""
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
            capture_output=True, text=True, timeout=10)
        cmd = (r.stdout or "").strip().lower()
    except Exception:
        return False
    return bool(cmd) and "run_server" in cmd


def check_single_instance(port: int, host: str) -> None:
    """Single-instance lock + stale-PID handling + port preflight.

    Refuses when a verified SNIPER server is already running or the port
    is taken; clears stale/foreign PID files WITHOUT terminating."""
    if os.path.exists(PID_FILE):
        try:
            pid = int((open(PID_FILE).read() or "0").strip() or 0)
        except ValueError:
            pid = 0
        if pid and pid != os.getpid() and pid_alive(pid):
            if pid_is_our_server(pid):
                raise LifecycleError(
                    f"ALREADY_RUNNING: SNIPER server PID {pid} is live — "
                    "second instance refused (single-instance lock)")
            print(f"[lifecycle] PID {pid} alive but NOT a SNIPER server — "
                  "PID file is foreign/stale: clearing lock file only "
                  "(no process terminated)")
            os.remove(PID_FILE)
        else:
            print(f"[lifecycle] PID file stale (pid={pid}) — clearing "
                  "(no process terminated)")
            os.remove(PID_FILE)
    # port preflight (bind test without SO_REUSEADDR -> fails if taken)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        raise LifecycleError(
            f"PORT_BUSY: {host}:{port} already bound by another process — "
            "refusing to start (use --port to choose another)")
    finally:
        probe.close()


# ------------------------------------------------------------------ shutdown
_shutting_down = False


def clean_shutdown(signum, _frame):
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    print(f"\n[lifecycle] signal {signum}: STOP NEW OPERATIONS -> FLUSH -> "
          "RELEASE LOCK -> REMOVE OWN PID -> EXIT")
    release_lock(only_own_pid=True)
    sys.exit(0)


def release_lock(only_own_pid: bool) -> None:
    if not os.path.exists(PID_FILE):
        return
    try:
        pid = int((open(PID_FILE).read() or "0").strip() or 0)
    except ValueError:
        pid = 0
    if only_own_pid and pid != os.getpid():
        print(f"[lifecycle] PID file belongs to {pid}, not us "
              f"({os.getpid()}) — leaving it untouched")
        return
    os.remove(PID_FILE)
    print(f"[lifecycle] lock released, pid file removed (pid {pid})")


# ------------------------------------------------------------------ cli
def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="SNIPER CashFlow — unified application server")
    ap.add_argument("--host", default=None,
                    help="bind host (overrides environment)")
    ap.add_argument("--port", type=int, default=None,
                    help="bind port (overrides environment)")
    return ap.parse_args(argv)


def resolve_bind(args) -> tuple:
    """Precedence: explicit --host/--port > WEB_HOST/WEB_PORT > PORT
    (PaaS) > default 127.0.0.1:8765. An explicit --port never gets
    silently ignored."""
    port_env = os.environ.get("WEB_PORT") or os.environ.get("PORT")
    port = args.port if args.port is not None else (
        int(port_env) if port_env else 8765)
    host = args.host if args.host is not None else (
        os.environ.get("WEB_HOST") or ("0.0.0.0" if (port_env and args.port is None) else "127.0.0.1"))
    return host, port


def _sha(path: str) -> str:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest().upper()[:24] + "…"
    except OSError:
        return "NOT_FOUND"


def startup_diagnostics(host: str, port: int) -> None:
    try:
        manifest = json.load(open(os.path.join(PROJECT_ROOT, "release_manifest.json"),
                                  encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    print("=" * 66)
    print("  SNIPER CashFlow — Unified Application Server")
    print("=" * 66)
    print(f"  PROJECT_ROOT         : {PROJECT_ROOT}")
    print(f"  SERVER_PID           : {os.getpid()}")
    print(f"  HOST:PORT            : {host}:{port}")
    print(f"  INSTANCE_LOCK        : {PID_FILE} ({LOCK_SENTINEL})")
    print(f"  RUNTIME_VERSION      : {manifest.get('project_version', 'unknown')}")
    print(f"  RELEASE_MANIFEST     : release_manifest.json")
    print(f"  MANIFEST_HASH        : "
          f"{_sha(os.path.join(PROJECT_ROOT, 'release_manifest.json'))}")
    print(f"  FROZEN_EVIDENCE_HASH : {_sha(os.path.join(PROJECT_ROOT, 'data', 'evidence_model', 'V1.68-EVIDENCE-MODEL-v1.0.json'))}")
    print(f"  Open                 : http://{host}:{port}")
    print(f"  API                  : http://{host}:{port}/api/health | /api/our_ea/health")
    print("=" * 66)


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv=None) -> int:
    args = parse_args(argv)
    host, port = resolve_bind(args)
    try:
        check_single_instance(port, host)
    except LifecycleError as ex:
        print(f"[lifecycle] START REFUSED: {ex}")
        return 2
    signal.signal(signal.SIGINT, clean_shutdown)
    signal.signal(signal.SIGTERM, clean_shutdown)
    if hasattr(signal, "SIGBREAK"):          # Windows CTRL_BREAK group
        signal.signal(signal.SIGBREAK, clean_shutdown)
    try:
        httpd = make_server(host, port, application,
                            server_class=ThreadingWSGIServer)
    except OSError as ex:
        print(f"[lifecycle] BIND FAILED: {ex}")
        return 3
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    startup_diagnostics(host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        release_lock(only_own_pid=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
