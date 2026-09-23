@echo off
rem SNIPER CashFlow - Web: START (or just open the browser if already running)
rem Stop with: stop_web.bat  (or close the minimized server console)
setlocal
cd /d "%~dp0"
set PORT=8765
if not "%WEB_PORT%"=="" set PORT=%WEB_PORT%

where curl >nul 2>nul
if errorlevel 1 (
  echo [WARN] curl not found - skipping the already-running check.
  goto :start
)

curl -s -o nul http://127.0.0.1:%PORT%/api/health
if not errorlevel 1 goto :open

:start
echo Starting SNIPER CashFlow Web (port %PORT%) ...
start "SNIPER Web Server" /min cmd /c python web\backend\run_server.py

set /a TRIES=0
:wait
ping -n 2 127.0.0.1 >nul
curl -s -o nul http://127.0.0.1:%PORT%/api/health
if not errorlevel 1 goto :open
set /a TRIES+=1
if %TRIES% LSS 15 goto :wait
echo [ERROR] the web server did not respond within 15 seconds.
pause
exit /b 1

:open
start "" http://127.0.0.1:%PORT%
echo.
echo   Web is running:  http://127.0.0.1:%PORT%
echo   The server runs in a minimized console window.
echo   To stop: use "SNIPER Web - Stop" (stop_web.bat) or close that console.
echo.
ping -n 4 127.0.0.1 >nul
endlocal
