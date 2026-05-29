@echo off
title Fiverr Automation - UI Dump
set /p label="Label for this dump (e.g. inbox, conversation, home): "
if "%label%"=="" set label=screen
python src\dump_ui.py --label "%label%"
echo.
pause
