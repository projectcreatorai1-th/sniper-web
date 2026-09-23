"""Create desktop shortcuts for the SNIPER web version (start / stop).

- "SNIPER Web - Start.lnk"  -> start_web.bat  (starts the server if needed,
  then opens the browser)
- "SNIPER Web - Stop.lnk"   -> stop_web.bat   (stops the server)
- Reuses the project icon generator from create_desktop_shortcut.py

Run:  python create_web_shortcuts.py
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from create_desktop_shortcut import ICON_PATH, verify_shortcut, write_icon  # noqa: E402

SHORTCUTS = [
    ("SNIPER Web - Start", os.path.join(ROOT, "start_web.bat"),
     "SNIPER CashFlow Web — start server + open browser"),
    ("SNIPER Web - Stop", os.path.join(ROOT, "stop_web.bat"),
     "SNIPER CashFlow Web — stop server"),
]


def _ps(script: str) -> str:
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "powershell failed")
    return proc.stdout.strip()


def create_shortcut(name: str, target: str, description: str) -> str:
    script = f"""
$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$ws = New-Object -ComObject WScript.Shell
$lnkPath = Join-Path $desktop '{name}.lnk'
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = '{target}'
$lnk.WorkingDirectory = '{ROOT}'
$lnk.IconLocation = '{ICON_PATH},0'
$lnk.Description = '{description}'
$lnk.Save()
Write-Output $lnkPath
"""
    return _ps(script)


def main() -> None:
    if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not os.path.exists(ICON_PATH):
        write_icon(ICON_PATH)
    ok_all = True
    for name, target, desc in SHORTCUTS:
        lnk = create_shortcut(name, target, desc)
        info = verify_shortcut(lnk)
        ok = os.path.exists(lnk) and os.path.exists(info.get("TargetPath", ""))
        ok_all = ok_all and ok
        print(f"{'OK  ' if ok else 'FAIL'} {lnk}")
        print(f"     -> {info.get('TargetPath')}")
    print("RESULT:", "OK" if ok_all else "FAILED")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
