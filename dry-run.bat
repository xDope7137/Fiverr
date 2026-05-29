@echo off
title Fiverr Automation - DRY RUN
echo ============================================================
echo  Fiverr Automation - DRY RUN
echo ============================================================
echo  Will scan for new contacts and walk through the flow,
echo  but will NOT actually send any messages.
echo.
echo  Press Ctrl+C in this window to stop.
echo ============================================================
echo.
python src\watch_and_reply.py --dry-run
echo.
pause
