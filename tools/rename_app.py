"""Rename 'SNIPER CashFlow Analyzer' -> 'SNIPER CashFlow' across the web side.

Desktop application files (desktop/, run_app.py, create_desktop_shortcut.py,
PROJECT_STATUS.md) and core logic are NOT touched - only core/report.py's two
user-visible report title strings change (display-only, no behavior).

Run: python tools/rename_app.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "web/backend/api.py",
    "web/backend/app.py",
    "web/backend/run_server.py",
    "web/frontend/app.js",
    "web/frontend/index.html",
    "web/frontend/manual.html",
    "web/frontend/style.css",
    "start_web.bat",
    "stop_web.bat",
    "create_web_shortcuts.py",
    "tools/runtime_check.py",
    "tests/web/test_web_http.py",
    "README.md",
    "DEPLOYMENT.md",
    "WEB_ARCHITECTURE.md",
    "WEB_STATUS.md",
    "core/report.py",
]

OLD = "SNIPER CashFlow Analyzer"
NEW = "SNIPER CashFlow"

for rel in FILES:
    path = os.path.join(ROOT, rel)
    with open(path, "rb") as f:
        data = f.read()
    text = data.decode("utf-8")
    count = text.count(OLD)
    if count == 0:
        print("skip (not found):", rel)
        continue
    text = text.replace(OLD, NEW)
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))
    print(f"replaced {count:2d}x: {rel}")
