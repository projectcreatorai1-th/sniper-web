"""Convert text files to CRLF line endings (Windows .bat requirement).

Usage: python tools/to_crlf.py file1 [file2 ...]
"""
import sys

for path in sys.argv[1:]:
    data = open(path, "rb").read()
    fixed = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    with open(path, "wb") as f:
        f.write(fixed)
    print("CRLF:", path, len(fixed), "bytes")
