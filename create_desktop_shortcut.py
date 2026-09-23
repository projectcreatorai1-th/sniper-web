"""Create a desktop shortcut for SNIPER CashFlow Analyzer.

- Generates assets/icon.ico (pure stdlib: hand-built ICO container with
  32x32 and 16x16 images - navy target/crosshair design)
- Creates "<Desktop>\\SNIPER CashFlow Analyzer.lnk" pointing to pythonw.exe
  (no console window) with the app icon and correct working directory
- Verifies the shortcut by reading it back

Run:  python create_desktop_shortcut.py
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(ROOT, "assets", "icon.ico")
SHORTCUT_NAME = "SNIPER CashFlow Analyzer"
APP_TITLE = "SNIPER CashFlow Analyzer — V1.68"

NAVY = (22, 33, 62)        # #16213e
GOLD = (201, 162, 39)      # #c9a227
GOLD_LIGHT = (217, 181, 63)


# ---------------------------------------------------------------------------
# ICO generation (no external dependency)
# ---------------------------------------------------------------------------
def _pixels(size: int):
    """Yield (x, y, rgb, alpha) for the target/crosshair design."""
    cx = (size - 1) / 2.0
    cy = cx
    ring_r = size * 0.34          # outer aim ring radius
    ring_t = max(1.0, size / 14.0)
    dot_r = max(0.9, size / 22.0)
    corner = max(2, size // 7)    # rounded-corner radius of the plate

    for y in range(size):
        for x in range(size):
            # rounded-square plate
            rx = min(x, size - 1 - x)
            ry = min(y, size - 1 - y)
            if rx < corner and ry < corner:
                dx, dy = corner - rx, corner - ry
                if dx * dx + dy * dy > corner * corner:
                    continue
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if abs(d - ring_r) <= ring_t / 2:
                yield x, y, GOLD, 255
            elif d <= dot_r:
                yield x, y, GOLD_LIGHT, 255
            elif (abs(x - cx) <= 0.6 or abs(y - cy) <= 0.6) and d <= ring_r - ring_t:
                yield x, y, GOLD, 255
            else:
                yield x, y, NAVY, 255


def _bmp_entry(size: int) -> bytes:
    """One ICO image: BITMAPINFOHEADER + bottom-up BGRA rows + AND mask."""
    px = {}
    for x, y, rgb, a in _pixels(size):
        px[(x, y)] = (rgb, a)
    xor = bytearray()
    for y in range(size - 1, -1, -1):          # bottom-up
        for x in range(size):
            (r, g, b), a = px.get((x, y), ((0, 0, 0), 0))
            xor += bytes((b, g, r, a))
    mask_row = ((size + 31) // 32) * 4
    and_mask = bytes(mask_row * size)          # 0 = use alpha channel
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         len(xor) + len(and_mask), 0, 0, 0, 0)
    return header + bytes(xor) + and_mask


def write_icon(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    images = [(32, _bmp_entry(32)), (16, _bmp_entry(16))]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    data = b""
    for size, blob in images:
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32,
                               len(blob), offset)
        data += blob
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(header + entries + data)


# ---------------------------------------------------------------------------
# Shortcut creation / verification
# ---------------------------------------------------------------------------
def _find_pythonw() -> str:
    exe = sys.executable
    candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(candidate):
        return candidate
    return exe  # fall back to console python (a console window will show)


def _ps(script: str) -> str:
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "powershell failed")
    return proc.stdout.strip()


def create_shortcut() -> str:
    pythonw = _find_pythonw()
    run_app = os.path.join(ROOT, "run_app.py")
    write_icon(ICON_PATH)
    # single-quoted PS strings; paths contain no single quotes
    script = f"""
$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$ws = New-Object -ComObject WScript.Shell
$lnkPath = Join-Path $desktop '{SHORTCUT_NAME}.lnk'
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = '{pythonw}'
$lnk.Arguments = '"{run_app}"'
$lnk.WorkingDirectory = '{ROOT}'
$lnk.IconLocation = '{ICON_PATH},0'
$lnk.Description = '{APP_TITLE}'
$lnk.Save()
Write-Output $lnkPath
"""
    return _ps(script)


def verify_shortcut(lnk_path: str) -> dict:
    script = f"""
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut('{lnk_path}')
Write-Output ('TargetPath=' + $lnk.TargetPath)
Write-Output ('Arguments=' + $lnk.Arguments)
Write-Output ('WorkingDirectory=' + $lnk.WorkingDirectory)
Write-Output ('IconLocation=' + $lnk.IconLocation)
"""
    out = _ps(script)
    info = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return info


def main() -> None:
    if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Generating icon ...", ICON_PATH)
    write_icon(ICON_PATH)
    print("Icon size:", os.path.getsize(ICON_PATH), "bytes")
    print("Creating desktop shortcut ...")
    lnk = create_shortcut()
    print("Shortcut:", lnk)
    info = verify_shortcut(lnk)
    ok = os.path.exists(lnk) and os.path.exists(info.get("TargetPath", ""))
    print("TargetPath:", info.get("TargetPath"))
    print("Arguments :", info.get("Arguments"))
    print("WorkDir   :", info.get("WorkingDirectory"))
    print("Icon      :", info.get("IconLocation"))
    print("RESULT:", "OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
