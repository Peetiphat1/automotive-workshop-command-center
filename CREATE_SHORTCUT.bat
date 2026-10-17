@echo off
setlocal
cd /d "%~dp0"
title Zero Garage - Create Shortcut

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
pause
