@echo off
echo ============================================================
echo Fiverr Automation - first time setup
echo ============================================================
echo.
echo [1/2] Installing Python dependencies...
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed.
    echo Check that Python 3.8+ is installed and `python --version` works.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo.
echo [2/2] Running preflight checks...
echo.
python preflight.py
echo.
echo Setup finished. Edit config.json (set "serial" and "message"),
echo then run dry-run.bat to see what would happen,
echo or start.bat to go live.
echo.
pause
