@echo off
echo ============================================================
echo Fiverr Automation - LIVE
echo ============================================================
echo Uses config.json. If "send": true, replies will be posted.
echo If "send": false, dry-run only.
echo Press Ctrl+C to stop.
echo.
python watch_and_reply.py
echo.
pause
