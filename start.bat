@echo off
title Fiverr Automation - Running
echo ============================================================
echo  Fiverr Automation
echo ============================================================
echo  Reading settings from config.json.
echo    - "send": true  -> actually posts replies
echo    - "send": false -> dry-run (no messages sent)
echo.
echo  Open the Fiverr app on the phone before starting.
echo  Press Ctrl+C in this window to stop.
echo ============================================================
echo.
python src\watch_and_reply.py
if errorlevel 1 (
    echo.
    echo [ERROR] Script exited with an error.
    echo Run check.bat to diagnose, or setup.bat if this is a fresh install.
)
echo.
pause
