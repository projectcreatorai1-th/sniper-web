@echo off
rem SNIPER CashFlow Analyzer - Web: STOP
rem Kills the web server started by start_web.bat - PID file first, then port lookup
setlocal
cd /d "%~dp0"
set PORT=8765
if not "%WEB_PORT%"=="" set PORT=%WEB_PORT%
set PIDFILE=web\backend\web_server.pid

if not exist "%PIDFILE%" goto :fallback

set /p PID=<"%PIDFILE%"
taskkill /PID %PID% /F >nul 2>nul
del "%PIDFILE%" >nul 2>nul
echo Web server stopped - PID %PID%.
ping -n 3 127.0.0.1 >nul
exit /b 0

:fallback
rem no PID file - e.g. server started before the PID feature - find it by port
set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /c:":%PORT% " ^| findstr /c:"LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
  echo Web server stopped - PID %%a listening on port %PORT%.
  set FOUND=1
)
if "%FOUND%"=="0" echo No running web server found.
ping -n 3 127.0.0.1 >nul
endlocal
