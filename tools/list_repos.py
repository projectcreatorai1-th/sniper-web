"""List the user's GitHub repos using the device-flow token (token not printed)."""
import json
import os
import urllib.request

TOKEN_FILE = os.path.join(os.environ["TEMP"], "sniper_gh_token.txt")
token = open(TOKEN_FILE, encoding="utf-8").read().strip()

req = urllib.request.Request("https://api.github.com/user",
                             headers={"Authorization": f"token {token}",
                                      "Accept": "application/vnd.github+json"})
with urllib.request.urlopen(req, timeout=20) as r:
    me = json.loads(r.read().decode("utf-8"))
print("login:", me.get("login"), "| name:", me.get("name"))

req = urllib.request.Request("https://api.github.com/user/repos?per_page=100&sort=updated",
                             headers={"Authorization": f"token {token}",
                                      "Accept": "application/vnd.github+json"})
with urllib.request.urlopen(req, timeout=20) as r:
    repos = json.loads(r.read().decode("utf-8"))
print("repos:", len(repos))
for repo in repos:
    print(f"  {repo['full_name']}  (default branch: {repo['default_branch']}, "
          f"updated {repo['updated_at']})")
