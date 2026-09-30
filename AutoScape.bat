@echo off
setlocal enabledelayedexpansion

:: Work from the directory containing this script so relative paths always resolve.
cd /d "%~dp0"
:: Window title lets Stop-AutoScape.bat find and close this console.
title AutoScape Launcher

echo.
echo  ==========================================
echo   AutoScape Launcher
echo  ==========================================
echo.

:: ---- Bootstrap: verify Python is present ----
where python >nul 2>&1
if errorlevel 1 (
    echo  ERROR: python not found on PATH.
    echo  AutoScape requires Python 3.12 or later.
    echo  See the Prerequisites section in RUN.md for installation instructions.
    echo.
    pause
    exit /b 1
)

:: ---- Bootstrap: verify Node and npm are present ----
where node >nul 2>&1
if errorlevel 1 (
    echo  ERROR: node not found on PATH.
    echo  AutoScape requires Node 20 or later ^(which includes npm^).
    echo  See the Prerequisites section in RUN.md for installation instructions.
    echo.
    pause
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo  ERROR: npm not found on PATH.
    echo  AutoScape requires Node 20 or later ^(which includes npm^).
    echo  See the Prerequisites section in RUN.md for installation instructions.
    echo.
    pause
    exit /b 1
)

:: ---- Bootstrap: uv ----
:: UV_CMD is either "uv" (on PATH) or "python -m uv" (--user install, PATH not yet updated).
:: Use "uv --version" instead of "where uv" to avoid spurious drive-probe errors on
:: systems where PATH contains disconnected or unavailable drive letters.
set "UV_CMD=uv"
uv --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=* delims=" %%V in ('uv --version 2^>^&1') do echo  [setup] uv found: %%V
) else (
    echo  [setup] uv not found -- installing via pip...
    python -m pip install --user uv
    if errorlevel 1 (
        echo.
        echo  ERROR: pip install uv failed. See the output above.
        echo  Manual install command: python -m pip install --user uv
        echo  See the Prerequisites section in RUN.md for instructions.
        echo.
        pause
        exit /b 1
    )
    :: After --user install, "uv" may not be on PATH yet in this session.
    :: Check the binary directly; if missing, fall back to the module form.
    uv --version >nul 2>&1
    if errorlevel 1 set "UV_CMD=python -m uv"
    for /f "tokens=* delims=" %%V in ('python -m uv --version 2^>^&1') do echo  [setup] uv installed: %%V
)

:: ---- Bootstrap: pnpm ----
:: PNPM_CMD is either "pnpm" (on PATH) or "npm exec pnpm --" (post-install PATH lag).
set "PNPM_CMD=pnpm"
where pnpm >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=* delims=" %%V in ('pnpm --version 2^>^&1') do echo  [setup] pnpm found: %%V
) else (
    echo  [setup] pnpm not found -- installing via npm...
    npm install -g pnpm
    if errorlevel 1 (
        echo.
        echo  ERROR: npm install -g pnpm failed. See the output above.
        echo  Manual install command: npm install -g pnpm
        echo  See the Prerequisites section in RUN.md for instructions.
        echo.
        pause
        exit /b 1
    )
    where pnpm >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=* delims=" %%V in ('pnpm --version 2^>^&1') do echo  [setup] pnpm installed: %%V
    ) else (
        set "PNPM_CMD=npm exec pnpm --"
        echo  [setup] pnpm installed ^(session PATH not updated; using npm exec pnpm as fallback^)
    )
)

echo.

:: ---- Configuration note ----
if exist "secrets" (
    echo  [setup] provider keys will be loaded from environment, optional backend\.env.local, and secrets\.
) else (
    echo  [setup] secrets\ not found; backend will rely on environment variables or optional backend\.env.local.
)

:: ---- Log file locations ----
:: Use the FULL %TEMP% path. (A previous version converted this to an 8.3 short
:: path via %%~sI, but on volumes where 8.3 name generation is disabled that
:: short name does not resolve, so the log files could not be created and the
:: tailer printed "The system cannot find the file ..." on every loop.) We quote
:: the paths everywhere so spaces are handled even if %TEMP% ever contains them.
:: Store logs inside the project under a RELATIVE path. We cd'd to the project
:: root at the top of this script, so ".runtime" always exists/writable here and a
:: relative path can never contain spaces -- even though the absolute project path
:: does. This avoids every prior failure mode: %TEMP% resolving to a non-resolvable
:: 8.3 short path, needing admin to write to C:\, and nested-quote redirect breakage.
:: The child processes (started with "cd /d backend"/"cd /d frontend") reach these
:: via "..\.runtime\..."; the reader (run from project root) uses ".runtime\...".
set "LOGDIR=.runtime"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "BLOG=%LOGDIR%\ascape_back.log"
set "FLOG=%LOGDIR%\ascape_front.log"

:: Path the CHILD shells use after they cd into backend\ / frontend\ (one level deep).
set "BLOG_CHILD=..\%LOGDIR%\ascape_back.log"
set "FLOG_CHILD=..\%LOGDIR%\ascape_front.log"

:: Pre-create the log files so they exist before the child processes start.
type nul > "%BLOG%"
type nul > "%FLOG%"

:: ---- Stop stale servers from a previous launch ----
:: Ctrl+C or a crash can orphan uvicorn/vite; a leftover listener would make this
:: run silently pick a different backend port. The script only kills processes
:: whose command line identifies them as AutoScape's own uvicorn/vite processes.
if exist "scripts\stop_stale_servers.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop_stale_servers.ps1"
)

:: ---- Port probe: find first free port in 8000-8010 ----
:: Write a temporary Python script into .runtime and run it to probe TCP ports.
(
echo import socket
echo import sys
echo for port in range^(8000, 8011^):
echo     try:
echo         s = socket.socket^(socket.AF_INET, socket.SOCK_STREAM^)
echo         s.bind^(^('127.0.0.1', port^)^)
echo         s.close^(^)
echo         print^(port^)
echo         sys.exit^(0^)
echo     except OSError:
echo         pass
) > "%LOGDIR%\ascape_probe.py"

set "CHOSEN_PORT="
for /f %%P in ('python "%LOGDIR%\ascape_probe.py"') do set "CHOSEN_PORT=%%P"
del "%LOGDIR%\ascape_probe.py" 2>nul

if not defined CHOSEN_PORT (
    echo.
    echo  ERROR: No available port found in range 8000-8010.
    echo  Please free up a port in that range and try again.
    echo.
    pause
    exit /b 1
)

:: Write the chosen port so vite.config.ts can wire the dev proxy to the right port.
:: Use a relative path -- we cd'd to the project root at the top of this script.
echo !CHOSEN_PORT!> "backend\.runtime-port"

:: ---- Frontend setup: remove conflicting npm lockfile ----
if exist "frontend\package-lock.json" del /q "frontend\package-lock.json"

:: ---- Frontend setup: detect and remove npm-created node_modules ----
:: Heuristic: npm creates .package-lock.json; pnpm creates .modules.yaml.
:: If the former exists and the latter does not, node_modules was created by npm
:: and must be removed before pnpm install can succeed cleanly.
if exist "frontend\node_modules\.package-lock.json" (
    if not exist "frontend\node_modules\.modules.yaml" (
        echo  [setup] Removing npm-created node_modules so pnpm can install cleanly...
        rmdir /s /q "frontend\node_modules"
    )
)

:: ---- Frontend setup: install dependencies ----
:: IMPORTANT: pnpm 10+ flags esbuild's build script as "ignored" and exits
:: non-zero -- but esbuild's prebuilt native binary is installed and vite runs
:: fine anyway. So we do NOT trust pnpm's exit code. We check whether the deps
:: actually landed (frontend\node_modules\vite exists), and we launch the dev
:: server with --config.verify-deps-before-run=false so pnpm does not re-run the
:: failing build gate on every "pnpm dev".
echo  [setup] Installing frontend dependencies...
call !PNPM_CMD! --dir frontend install

if not exist "frontend\node_modules\vite" (
    echo  [setup] Dependencies missing -- doing a clean reinstall...
    if exist "frontend\node_modules" rmdir /s /q "frontend\node_modules"
    if exist "frontend\package-lock.json" del /q "frontend\package-lock.json"
    call !PNPM_CMD! --dir frontend install
)
if not exist "frontend\node_modules\vite" (
    echo.
    echo  ERROR: frontend dependencies failed to install.
    echo  Manual fix:
    echo    cd frontend
    echo    rmdir /s /q node_modules
    echo    pnpm install
    echo.
    echo  ^(The "Ignored build scripts: esbuild" line is expected and harmless.^)
    echo.
    pause
    exit /b 1
)

:: ---- Start backend ----
:: start /b keeps both processes in this console group so they are automatically
:: terminated when this console window is closed (Windows kills the whole group).
:: Use relative "cd /d backend" -- the new cmd.exe inherits our project-root cwd.
echo  [AutoScape] Backend on http://localhost:!CHOSEN_PORT!
:: No --reload here: the launcher is for running the app, not editing it, and uvicorn's
:: file watcher has been seen to print "Reloading..." and never restart on Windows,
:: leaving stale code serving. Developers use the two-terminal flow in RUN.md instead.
start /b "" cmd /c "cd /d backend && !UV_CMD! run uvicorn app.main:app --port !CHOSEN_PORT! >> !BLOG_CHILD! 2>&1"

:: ---- Start frontend ----
echo  [AutoScape] Starting frontend on port 5173...
start /b "" cmd /c "cd /d frontend && !PNPM_CMD! --config.verify-deps-before-run=false dev >> !FLOG_CHILD! 2>&1"

:: ---- Wait for both services, open the browser, and stream the logs ----
:: Done in PowerShell (scripts\wait_and_tail.ps1): cmd's "for /f" cannot read a log
:: file while the service holds it open for writing and misreports it as missing,
:: which produced "The system cannot find the file .runtime\ascape_back.log" on
:: every tick. .NET reads shared files fine, and the script also strips Vite's
:: colour codes. It returns 1 if the services never came up.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\wait_and_tail.ps1" -BackendPort !CHOSEN_PORT! -BackLog "!BLOG!" -FrontLog "!FLOG!"
if errorlevel 1 (
    echo.
    echo  Press any key to close this window.
    pause > nul
    exit /b 1
)
exit /b 0
