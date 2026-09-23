@echo off
rem Push the SNIPER project to GitHub (a GitHub login window may appear - click Sign in / Authorize)
setlocal
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

if not exist .git (
  echo [ERROR] no local git repository found in this folder.
  pause
  exit /b 1
)

echo Pushing to github.com/projectcreatorail-th/sniper-web ...
echo (a GitHub login window may pop up - please Sign in / Authorize)
echo.
git push -u origin main --force
if errorlevel 1 (
  echo.
  echo [FAILED] - if it says "Repository not found", the account or repo name differs.
  echo Check the GitHub page in your browser and tell the assistant the exact owner/repo.
)
echo.
echo Done. You can close this window.
pause
