"""Store the device-flow token in Git Credential Manager and push to GitHub.

The token is read from %TEMP%\\sniper_gh_token.txt (never printed).

Run: python tools\\push_with_device_token.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(os.environ["TEMP"], "sniper_gh_token.txt")
GIT = r"C:\Program Files\Git\cmd\git.exe"
ENV = dict(os.environ, PATH=r"C:\Program Files\Git\cmd;" + os.environ.get("PATH", ""),
           GCM_INTERACTIVE="never", GIT_TERMINAL_PROMPT="0")

with open(TOKEN_FILE, encoding="utf-8") as f:
    token = f.read().strip()
if not token:
    print("no token file")
    sys.exit(1)

# 1) store the credential so later git commands work without prompts
cred_input = ("protocol=https\nhost=github.com\n"
              "username=projectcreatorail-th\n"
              f"password={token}\n\n").encode()
r = subprocess.run([GIT, "credential", "approve"], input=cred_input,
                   capture_output=True, env=ENV, cwd=ROOT)
if r.returncode != 0:
    print("credential approve failed:", r.stderr.decode(errors="replace"))
    sys.exit(1)
print("credential stored")

# 2) push
r = subprocess.run([GIT, "push", "-u", "origin", "main", "--force"],
                   capture_output=True, env=ENV, cwd=ROOT, text=True)
out = (r.stdout or "") + (r.stderr or "")
# hide anything that looks like a token just in case
out = out.replace(token, "***")
print(out[-1500:])
print("PUSH_RC", r.returncode)

# 3) verify remote head
r2 = subprocess.run([GIT, "ls-remote",
                     "https://github.com/projectcreatorail-th/sniper-web.git",
                     "refs/heads/main"],
                    capture_output=True, env=ENV, cwd=ROOT, text=True)
print("REMOTE:", r2.stdout.strip() or r2.stderr.strip()[:200])
sys.exit(0 if (r.returncode == 0 and "main" in r2.stdout) else 1)
