"""Inspect a GitHub repo tree to find where run_server.py actually landed."""
import json
import os
import sys
import urllib.request

url = "https://api.github.com/repos/projectcreatorail-th/sniper-web/git/trees/main?recursive=1"
try:
    with urllib.request.urlopen(url, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8"))
except Exception as exc:
    print("request failed:", exc)
    sys.exit(1)

if "tree" not in d:
    print("API says:", d.get("message", d))
    sys.exit(0)

paths = [t["path"] for t in d["tree"]]
print("total files:", len(paths))
print("key files:")
for p in paths:
    if p.endswith(("run_server.py", "requirements.txt", "app.js")):
        print("  ", p)
print("first 12 paths:")
for p in paths[:12]:
    print("  ", p)
