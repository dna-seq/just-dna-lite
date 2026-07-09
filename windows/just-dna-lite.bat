@echo off
setlocal enabledelayedexpansion

title Just DNA Lite

set "APP_DIR=%~dp0app"
set "UV=%~dp0uv.exe"

REM Export the bundled uv.exe path so the Python process can locate it
REM even when uv is not in PATH (typical on a fresh Windows install)
set "JUST_DNA_UV_EXE=%~dp0uv.exe"

REM Switch terminal to UTF-8 to correctly render emojis and box-drawing characters
chcp 65001 >nul

REM Ensure Python output is visible immediately
set PYTHONUNBUFFERED=1
REM Force UTF-8 encoding so emoji in typer output don't crash on Windows cmd.exe (cp1252)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM Enable Dagster compute log capture on Windows
set PYTHONLEGACYWINDOWSSTDIO=1

REM Kill orphan processes on startup to prevent port collisions
set JUST_DNA_START_KILL_PORTS=true

echo.
echo  ============================================
echo    Just DNA Lite - Genome Analysis Tool
echo  ============================================
echo.

cd /d "%APP_DIR%"
if errorlevel 1 (
    echo ERROR: Application directory not found: %APP_DIR%
    echo Please reinstall Just DNA Lite.
    pause
    exit /b 1
)

if not exist "%UV%" (
    echo ERROR: uv.exe not found at: %UV%
    echo Please reinstall Just DNA Lite.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo  First launch detected - setting up environment...
    echo  This downloads Python and dependencies ^(~1-2 GB^).
    echo  Please wait, this only happens once.
    echo.
    "%UV%" sync
    if errorlevel 1 (
        echo.
        echo ERROR: Environment setup failed.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
    echo.
    echo  Environment setup complete.
    echo.
) else (
    echo  Environment found. Starting...
    echo.
)

echo  Starting Just DNA Lite...
echo  The browser will open automatically when ready.
echo  Press Ctrl+C to stop the server.
echo.

start "" cmd /c "timeout /t 25 /nobreak >nul && start http://localhost:3000"

"%UV%" run python -m just_dna_lite.cli start
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% neq 0 (
    echo.
    echo  Just DNA Lite exited with error code %EXIT_CODE%.
    echo  Check the output above for details.
    pause
)
exit /b %EXIT_CODE%
