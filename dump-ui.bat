@echo off
set /p label="Label for this dump (e.g. inbox, conversation, home): "
if "%label%"=="" set label=screen
python dump_ui.py --label "%label%"
echo.
pause
