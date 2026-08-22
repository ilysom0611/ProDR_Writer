@echo off
rem ProDR_Writer one-click installer (Windows)
cd /d "%~dp0"
where python >/dev/null 2>/dev/null || (echo [ERROR] Python 3.10+ is required. Install from https://www.python.org/downloads/ & exit /b 1)
echo ==^> Creating virtual environment (.venv)
python -m venv .venv
echo ==^> Installing ProDR_Writer and dependencies
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\pip install -e . -q
if errorlevel 1 (echo [ERROR] Installation failed. & exit /b 1)
echo.
echo [OK] Installation complete.
echo   Start:  start.bat    (web UI, default http://127.0.0.1:8000^)
echo   Stop:   stop.bat
echo   Update: update.bat
