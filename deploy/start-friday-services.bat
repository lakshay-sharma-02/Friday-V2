@echo off
REM Friday V2 - Start all services
REM Runs watcher (Telegram auto-download) in the background

set PROJECT_DIR=%~dp0..
set VENV=%PROJECT_DIR%\.venv\Scripts\python.exe

echo Starting Friday services...

REM Kill any existing instances
taskkill /F /IM python.exe >nul 2>&1

REM Start the watcher (polls Telegram every 30s)
start "Friday Watcher" /MIN cmd /c "cd /d %PROJECT_DIR% && %VENV% -m friday.watcher --poll 30"

echo Watcher started.
echo.
echo To stop: taskkill /F /IM python.exe
