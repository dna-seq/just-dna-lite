@echo off
setlocal enabledelayedexpansion

title Just DNA Lite

set "APP_DIR=%~dp0app"
set "UV=%~dp0uv.exe"

REM Typer and Rich print emoji and box-drawing characters; cmd.exe's default code page (cp1252)
REM cannot encode them and the launcher crashes on its first line of output.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

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
)

REM Always sync: a no-op when the environment is current, and it finishes a first launch that
REM was interrupted (a half-built .venv used to be mistaken for a finished one).
"%UV%" sync --frozen
if errorlevel 1 (
    echo.
    echo ERROR: Environment setup failed.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

echo  Starting Just DNA Lite...
echo  The browser will open automatically when ready.
echo  Press Ctrl+C to stop the server.
echo.

start "" cmd /c "timeout /t 25 /nobreak >nul && start http://localhost:3000"

REM `python -m`, not `uv run start`: start.exe is a uv-generated wrapper that AppLocker and
REM Smart App Control block on machines without admin rights.
"%UV%" run --frozen python -m just_dna_lite.cli start
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% neq 0 (
    echo.
    echo  Just DNA Lite exited with error code %EXIT_CODE%.
    echo  Check the output above for details.
    pause
)
exit /b %EXIT_CODE%
