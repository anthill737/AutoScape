setlocal enabledelayedexpansion

:: Work from the directory containing this script so relative paths always resolve.
cd /d "%~dp0"

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
    :: On Windows, --user installs may land in a directory not yet on the current
    :: session's PATH. Use the module form to check without probing drive letters.
    python -m uv --version >nul 2>&1
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

:: ---- Derive short-form (8.3) path for TEMP to avoid space issues in log paths ----
for %%I in ("%TEMP%") do set "TDIR=%%~sI"

:: Log files land in %TEMP% so they don't clutter the project root.
set "BLOG=%TDIR%\ascape_back.log"
set "FLOG=%TDIR%\ascape_front.log"

:: Pre-create log files before starting child processes so the log tailer never
:: encounters a missing file during the startup window.
type nul > "%BLOG%"
type nul > "%FLOG%"

:: ---- Port probe: find first free port in 8000-8010 ----
:: Write a temporary Python script to %TEMP% and run it to probe TCP ports.
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
) > "%TDIR%\ascape_probe.py"

set "CHOSEN_PORT="
for /f %%P in ('python "%TDIR%\ascape_probe.py"') do set "CHOSEN_PORT=%%P"
del "%TDIR%\ascape_probe.py" 2>nul

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
:: Use --dir to target the frontend folder directly without pushd/popd,
:: which can fail if the path contains characters that confuse cmd.exe.
echo  [setup] Installing frontend dependencies...
!PNPM_CMD! --dir frontend install
if errorlevel 1 (
    echo.
    echo  ERROR: pnpm install failed. See the output above.
    echo  Try deleting frontend\node_modules and running AutoScape.bat again.
    echo.
    pause
    exit /b 1
)

:: ---- Start backend ----
:: start /b keeps both processes in this console group so they are automatically
:: terminated when this console window is closed (Windows kills the whole group).
:: Use relative "cd /d backend" -- the new cmd.exe inherits our project-root cwd.
echo  [AutoScape] Backend on http://localhost:!CHOSEN_PORT!
start /b "" cmd /c "cd /d backend && !UV_CMD! run uvicorn app.main:app --reload --port !CHOSEN_PORT! >> %BLOG% 2>&1"

:: ---- Start frontend ----
echo  [AutoScape] Starting frontend on port 5173...
start /b "" cmd /c "cd /d frontend && !PNPM_CMD! dev >> %FLOG% 2>&1"

echo.
echo  Waiting for frontend to be ready at http://localhost:5173
echo  Log output from both services appears below.
echo  ^(Close this window at any time to stop backend and frontend.^)
echo.

:: ---- Poll until frontend responds, streaming logs meanwhile (max ~2 min) ----
set /a BEND=0
set /a FEND=0
set /a WAIT=0

:wait_loop
ping -n 2 127.0.0.1 > nul
call :show_new_logs
set /a WAIT+=1
if !WAIT! GTR 60 goto timeout_error
curl -s --connect-timeout 1 http://localhost:5173 > nul 2>&1
if !errorlevel! equ 0 goto frontend_ready
goto wait_loop

:timeout_error
echo.
echo  ERROR: Frontend did not respond within ~2 minutes.
echo  Review the [frontend] log lines above for details.
echo  Common causes:
echo    - Port 5173 is already in use by another application
echo    - pnpm is not installed         ^(fix: npm install -g pnpm^)
echo    - Frontend dependencies missing  ^(fix: cd frontend ^&^& pnpm install^)
echo.
echo  Press any key to close this window.
pause > nul
exit /b 1

:frontend_ready
start "" "http://localhost:5173"
echo.
echo  ==========================================
echo   Both services are running.
echo   Close this window to stop everything.
echo  ==========================================
echo.

:: ---- Stream labeled log output until the window is closed ----
:log_loop
call :show_new_logs
ping -n 2 127.0.0.1 > nul
goto log_loop

:: ---- Subroutine: print any new lines from each log with a service prefix ----
:show_new_logs
set /a BLINE=0
for /f "usebackq tokens=* delims= eol=^" %%A in ("%BLOG%") do (
    set /a BLINE+=1
    if !BLINE! GTR !BEND! echo [backend] %%A
)
if !BLINE! GTR !BEND! set BEND=!BLINE!

set /a FLINE=0
for /f "usebackq tokens=* delims= eol=^" %%A in ("%FLOG%") do (
    set /a FLINE+=1
    if !FLINE! GTR !FEND! echo [frontend] %%A
)
if !FLINE! GTR !FEND! set FEND=!FLINE!
exit /b 0
