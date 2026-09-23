"""Build a clean GitHub-upload folder for deploying the web version.

Creates Desktop/sniper-web-upload/ containing only what the server needs
(core + web + tests + tools + runners + docs), without __pycache__, local
data, or desktop-only utilities.

Run:  python tools/make_github_upload.py
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(os.path.expanduser("~"), "Desktop", "sniper-web-upload")

INCLUDE_DIRS = ["core", "web", "tests", "tools"]
INCLUDE_FILES = [
    "README.md", "requirements.txt", ".gitignore", "run_tests.py",
    "run_web_tests.py", "DEPLOYMENT.md", "WEB_ARCHITECTURE.md", "WEB_STATUS.md",
]
EXCLUDE_PARTS = {"__pycache__"}


def copy_tree(src: str, dst: str) -> int:
    os.makedirs(dst, exist_ok=True)
    count = 0
    for name in os.listdir(src):
        if name in EXCLUDE_PARTS or name.endswith((".pyc", ".pid")):
            continue
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            os.makedirs(d, exist_ok=True)
            count += copy_tree(s, d)
        else:
            shutil.copy2(s, d)
            count += 1
    return count


def main() -> None:
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST)
    total = 0
    for d in INCLUDE_DIRS:
        total += copy_tree(os.path.join(ROOT, d), os.path.join(DEST, d))
    for f in INCLUDE_FILES:
        src = os.path.join(ROOT, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DEST, f))
            total += 1
        else:
            print("missing:", f)
    print(f"OK: {total} files -> {DEST}")


if __name__ == "__main__":
    main()
