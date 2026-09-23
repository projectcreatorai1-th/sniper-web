"""Per-line paren depth report for a line range of app.js.

Usage: python tools/line_depth.py <start> <end>
"""
import sys

start = int(sys.argv[1]) if len(sys.argv) > 1 else 525
end = int(sys.argv[2]) if len(sys.argv) > 2 else 552
src = open("web/frontend/app.js", encoding="utf-8").read().splitlines()
text = "\n".join(src[start - 1:end])
depth = 0
line = start
in_str = None
i = 0
seg_start = 0
while i < len(text):
    ch = text[i]
    if ch == "\n":
        seg = text[seg_start:i]
        print(f"{line:4d} {depth:+d}  {seg.strip()[:72]}")
        line += 1
        seg_start = i + 1
    if in_str:
        if ch == "\\":
            i += 2
            continue
        if ch == in_str:
            in_str = None
    else:
        if ch in ('"', "'", "`"):
            in_str = ch
        elif ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    i += 1
