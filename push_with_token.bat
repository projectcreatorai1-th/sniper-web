@echo off
rem Push to GitHub using a Personal Access Token (no login windows needed).
rem Steps: create a token at GitHub Settings -> Developer settings ->
rem Personal access tokens -> Tokens (classic) -> Generate (tick "repo"),
rem then run this file and paste the token when asked.
setlocal
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

echo Paste your GitHub token below (starts with ghp_ ) then press Enter.
echo (the token will be visible on screen - that is OK on your own PC)
set /p TOKEN=Token: 

if "%TOKEN%"=="" (
  echo No token entered. Bye.
  pause
  exit /b 1
)

echo.
echo Pushing ...
git push https://%TOKEN%@github.com/projectcreatorail-th/sniper-web.git main --force
if errorlevel 1 (
  echo.
  echo [FAILED] - token may be wrong or missing "repo" permission.
) else (
  echo.
  echo [SUCCESS] - code is on GitHub. You can close this window.
)
pause
