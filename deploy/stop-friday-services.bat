@echo off
echo Stopping Friday services...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM lt.exe >nul 2>&1
echo Done.
