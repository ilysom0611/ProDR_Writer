@echo off
setlocal
rem ProDR_Writer one-click installer (Windows)
cd /d "%~dp0"

where python >nul 2>nul || (echo [ERROR] Python 3.10+ is required. Install from https://www.python.org/downloads/ & exit /b 1)

rem Reject the Windows Store python stub (it exists but only opens the Store)
python -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 'python' is not a working interpreter - this is usually the Windows Store stub.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    exit /b 1
)

rem Require Python 3.10 or newer
python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required. Your version:
    python --version
    exit /b 1
)

echo ==^> Creating virtual environment (.venv)
if exist .venv\Scripts\python.exe (
    echo      Reusing existing .venv
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
)

echo ==^> Installing ProDR_Writer and dependencies
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\pip install -e . -q
if errorlevel 1 (
    echo [ERROR] Installation failed.
    exit /b 1
)
echo.
echo [OK] Installation complete.
echo   Start:  start.bat    (web UI, default http://127.0.0.1:8000^)
echo   Stop:   stop.bat
echo   Update: update.bat
endlocal
