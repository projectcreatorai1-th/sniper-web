"""Check paren AND brace/bracket balance in a JS file (strings/comments aware)."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "app.js"
src = open(path, encoding="utf-8").read()
pairs = {")": "(", "}": "{", "]": "["}
stack = []
line = 1
in_str = None
i = 0
while i < len(src):
    ch = src[i]
    if ch == "\n":
        line += 1
    if in_str:
        if ch == "\\":
            i += 2
            continue
        if ch == in_str:
            in_str = None
    else:
        if ch in ('"', "'", "`"):
            in_str = ch
        elif ch == "/" and i + 1 < len(src) and src[i + 1] == "/":
            while i < len(src) and src[i] != "\n":
                i += 1
            continue
        elif ch == "/" and i + 1 < len(src) and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            line += src.count("\n", i, j if j != -1 else len(src))
            i = (j + 2) if j != -1 else len(src)
            continue
        elif ch in "([{":
            stack.append((ch, line))
        elif ch in ")]}":
            if not stack or stack[-1][0] != pairs[ch]:
                print(f"MISMATCH {ch!r} at line {line}, stack top: {stack[-1] if stack else None}")
                sys.exit(1)
            stack.pop()
    i += 1
if stack:
    print("UNCLOSED:", stack[-5:])
    sys.exit(1)
print("balanced (parens, braces, brackets)")
