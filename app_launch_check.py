import subprocess, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
p = subprocess.Popen([sys.executable, "run_app.py"],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(6)
alive = p.poll() is None
if alive:
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
out, err = p.communicate()
print("APP RUNNING:", alive)
print("STDERR:", (err or b"").decode(errors="replace")[:800] or "(empty)")
sys.exit(0 if alive and not (err or b"").strip() else 1)
