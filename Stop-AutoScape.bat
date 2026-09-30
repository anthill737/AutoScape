@echo off
:: Stop AutoScape: backend, frontend, their wrapper shells, and any launcher windows.
:: Double-click this, or run "Stop-AutoScape.bat" from a prompt.
:: Add /dry to see what would be stopped without stopping anything.
cd /d "%~dp0"
title AutoScape Stop

echo.
echo  ==========================================
echo   Stopping AutoScape
echo  ==========================================
echo.

set "DRY="
if /i "%~1"=="/dry" set "DRY=-DryRun"
if /i "%~1"=="--dry-run" set "DRY=-DryRun"

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop_autoscape.ps1" %DRY%

echo.
if defined DRY (
    echo  Dry run only. Nothing was stopped.
    pause
) else (
    echo  Done. This window closes in 3 seconds.
    ping -n 4 127.0.0.1 > nul
)
exit /b 0
