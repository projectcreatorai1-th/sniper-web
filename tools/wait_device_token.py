"""Poll GitHub device-flow token endpoint until the user authorizes.

Writes the token to %TEMP%\\sniper_gh_token.txt on success (never stdout).
Run: python tools\\wait_device_token.py
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

CLIENT_ID = "178c6fc778ccc68e1d6a"
CODE_FILE = os.path.join(os.environ["TEMP"], "device_code.json")
OUT = os.path.join(os.environ["TEMP"], "sniper_gh_token.txt")

with open(CODE_FILE, encoding="utf-8") as f:
    dev = json.load(f)

data = urllib.parse.urlencode({
    "client_id": CLIENT_ID,
    "device_code": dev["device_code"],
    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
}).encode()

deadline = time.time() + min(dev["expires_in"], 840)
interval = dev.get("interval", 5)

while time.time() < deadline:
    req = urllib.request.Request(
        "https://github.com/login/oauth/access_token", data=data,
        headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        print("request error:", exc)
        time.sleep(interval)
        continue
    err = resp.get("error")
    if err == "authorization_pending":
        print("pending...", flush=True)
        time.sleep(interval)
        continue
    if err == "slow_down":
        interval += 5
        time.sleep(interval)
        continue
    if err:
        print("FAILED:", err)
        sys.exit(1)
    token = resp.get("access_token")
    if token:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(token)
        print("TOKEN_RECEIVED")
        sys.exit(0)

print("EXPIRED")
sys.exit(1)
