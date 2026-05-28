@echo off
echo ============================================================
echo Fiverr Automation - DRY RUN
echo ============================================================
echo Will detect new contacts and walk through the flow,
echo but will NOT actually send any messages.
echo Press Ctrl+C to stop.
echo.
python watch_and_reply.py --dry-run
echo.
pause
