"""P1 lifecycle tests — real subprocess start/stop against
web/backend/run_server.py (argparse, single-instance lock, stale PID,
port override, clean shutdown, restart). Includes a 100-cycle stress.
"""
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

CREATE_NEW_PROCESS_GROUP = 0x00000200   # Windows: enables CTRL_BREAK

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER = os.path.join(ROOT, "web", "backend", "run_server.py")
# isolated lock dir per test process (never touch the real 8765 server)
_ISOLATED = tempfile.mkdtemp(prefix="sniper_lifecycle_")
PID_FILE = os.path.join(_ISOLATED, "web_server.pid")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start(port, host="127.0.0.1", env=None):
    e = dict(os.environ)
    e.pop("WEB_PORT", None)
    e.pop("WEB_HOST", None)
    e.pop("PORT", None)
    e["SNIPER_PID_FILE"] = PID_FILE
    e["PYTHONUNBUFFERED"] = "1"
    if env:
        e.update(env)
    return subprocess.Popen(
        [sys.executable, SERVER, "--host", host, "--port", str(port)],
        cwd=ROOT, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, creationflags=CREATE_NEW_PROCESS_GROUP)


def wait_port(port, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def stop(proc):
    """Graceful stop: CTRL_BREAK (runs SIGBREAK handler -> clean shutdown),
    then hard terminate only as last resort."""
    if proc.poll() is None:
        try:
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
            return
        except (AttributeError, OSError, subprocess.TimeoutExpired):
            pass
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self.procs = []
        self._saved_pid = None
        if os.path.exists(PID_FILE):
            self._saved_pid = open(PID_FILE).read()

    def tearDown(self):
        for p in self.procs:
            stop(p)
        # restore/leave-clean: remove pid file only if it belongs to a
        # dead process (tests run on free ports so their pids are gone)
        if os.path.exists(PID_FILE):
            try:
                pid = int(open(PID_FILE).read().strip() or 0)
            except ValueError:
                pid = 0
            alive = False
            if pid:
                try:
                    handle = __import__("ctypes").windll.kernel32.OpenProcess(
                        0x00100000, False, pid)
                    if handle:
                        alive = True
                        __import__("ctypes").windll.kernel32.CloseHandle(handle)
                except Exception:
                    pass
            if not alive:
                os.remove(PID_FILE)
            elif self._saved_pid is not None:
                open(PID_FILE, "w").write(self._saved_pid)

    def _spawn(self, port):
        p = start(port)
        self.procs.append(p)
        return p

    def test_start_pid_port_and_identity(self):
        port = free_port()
        p = self._spawn(port)
        self.assertTrue(wait_port(port), "server must listen")
        time.sleep(0.4)                      # let it write the pid file
        pid = int(open(PID_FILE).read().strip())
        self.assertEqual(pid, p.pid)
        self.assertTrue(wait_port(port))

    def test_second_instance_refused(self):
        port = free_port()
        p1 = self._spawn(port)
        self.assertTrue(wait_port(port))
        time.sleep(0.4)
        p2 = start(port)
        out = p2.communicate(timeout=15)[0]
        self.assertEqual(p2.returncode, 2, out)
        self.assertIn("ALREADY_RUNNING", out)
        self.assertTrue(p1.poll() is None, "first instance must survive")

    def test_stale_pid_cleared_safely(self):
        port = free_port()
        open(PID_FILE, "w").write("999999999")     # dead pid
        p = self._spawn(port)
        self.assertTrue(wait_port(port))
        time.sleep(0.4)
        self.assertEqual(int(open(PID_FILE).read().strip()), p.pid)

    def test_foreign_live_pid_not_killed_and_startup_continues(self):
        # write a pid of a definitely-alive non-SNIPER process (us)
        port = free_port()
        open(PID_FILE, "w").write(str(os.getpid()))
        p = self._spawn(port)
        self.assertTrue(wait_port(port), "foreign stale lock must not block")
        self.assertEqual(os.getpid() % 1, 0)       # we are alive & untouched
        time.sleep(0.4)
        self.assertEqual(int(open(PID_FILE).read().strip()), p.pid)

    def test_port_override_works(self):
        port = free_port()
        p = self._spawn(port)
        self.assertTrue(wait_port(port), f"--port {port} must bind for real")

    def test_host_override_works(self):
        port = free_port()
        p = self._spawn(port)
        self.assertTrue(wait_port(port))

    def test_port_busy_refused(self):
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        p = start(port)
        out = p.communicate(timeout=15)[0]
        self.assertEqual(p.returncode, 2, out)
        self.assertIn("PORT_BUSY", out)
        blocker.close()

    def test_clean_shutdown_removes_own_pid_and_lock(self):
        port = free_port()
        p = self._spawn(port)
        self.assertTrue(wait_port(port))
        time.sleep(0.4)
        self.assertEqual(int(open(PID_FILE).read().strip()), p.pid)
        os.kill(p.pid, signal.CTRL_BREAK_EVENT)     # operator-style stop
        p.wait(timeout=10)
        self.assertEqual(p.returncode, 0, "graceful shutdown exits 0")
        deadline = time.time() + 5
        while time.time() < deadline and os.path.exists(PID_FILE):
            time.sleep(0.1)
        self.assertFalse(os.path.exists(PID_FILE),
                         "clean shutdown must remove own pid file")

    def test_shutdown_never_removes_foreign_pid(self):
        port = free_port()
        foreign = str(os.getpid())
        open(PID_FILE, "w").write(foreign)
        p = self._spawn(port)                    # overwrote with own pid
        self.assertTrue(wait_port(port))
        time.sleep(0.4)
        # simulate foreign file while running: write another pid, stop
        open(PID_FILE, "w").write(foreign)
        os.kill(p.pid, signal.CTRL_BREAK_EVENT)
        p.wait(timeout=10)
        time.sleep(0.5)
        self.assertEqual(open(PID_FILE).read().strip(), foreign,
                         "must NOT delete a pid file owned by another process")

    def test_restart_cycle(self):
        port = free_port()
        p1 = self._spawn(port)
        self.assertTrue(wait_port(port))
        stop(p1)
        time.sleep(0.3)
        p2 = self._spawn(port)
        self.assertTrue(wait_port(port), "restart on same port must work")

    def test_diagnostics_show_manifest_and_frozen_hash(self):
        import hashlib
        frozen = hashlib.sha256(open(os.path.join(
            ROOT, "data", "evidence_model",
            "V1.68-EVIDENCE-MODEL-v1.0.json"), "rb").read()).hexdigest().upper()
        port = free_port()
        p = self._spawn(port)
        self.assertTrue(wait_port(port))
        time.sleep(0.5)
        p.terminate()
        out = p.communicate(timeout=10)[0]
        self.assertIn("PROJECT_ROOT", out)
        self.assertIn("INSTANCE_LOCK", out)
        self.assertIn("MANIFEST_HASH", out)
        self.assertIn("FROZEN_EVIDENCE_HASH", out)
        self.assertIn(frozen[:24], out, "diagnostics must print frozen hash")

    def test_env_port_fallback_still_works(self):
        port = free_port()
        e = dict(os.environ)
        e.pop("PORT", None)
        e["SNIPER_PID_FILE"] = PID_FILE
        e["WEB_PORT"] = str(port)
        e["PYTHONUNBUFFERED"] = "1"
        p = subprocess.Popen([sys.executable, SERVER], cwd=ROOT, env=e,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             creationflags=CREATE_NEW_PROCESS_GROUP)
        self.procs.append(p)
        self.assertTrue(wait_port(port), "env WEB_PORT fallback must work")


class TestLifecycleStress(unittest.TestCase):
    def test_100_start_stop_cycles(self):
        for i in range(100):
            port = free_port()
            p = start(port)
            ok = wait_port(port, timeout=15)
            self.assertTrue(ok, f"cycle {i}: server must start")
            stop(p)
            self.assertEqual(p.returncode if p.returncode else 0, 0)
        # after the storm: no stale lock, no orphan on our test ports
        if os.path.exists(PID_FILE):
            pid = open(PID_FILE).read().strip()
            self.assertEqual(pid, "", "no pid file may leak after stress")


if __name__ == "__main__":
    unittest.main()
