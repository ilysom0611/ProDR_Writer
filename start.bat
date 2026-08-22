@echo off
rem Start the ProDR_Writer web UI in a minimized window
cd /d "%~dp0"
if not exist .venv\Scripts\python (echo [ERROR] Not installed yet - run install.bat first. & exit /b 1)
if "%PRODR_PORT%"=="" set PRODR_PORT=8000
if "%PRODR_HOST%"=="" set PRODR_HOST=127.0.0.1
start "ProDR_Writer" /min cmd /c ".venv\Scripts\python -m prodr_writer web --host %PRODR_HOST% --port %PRODR_PORT% ^> prodr-web.log 2^>^&1"
timeout /t 3 /nobreak >nul
echo [OK] Started: http://%PRODR_HOST%:%PRODR_PORT%  (log: prodr-web.log, window title: ProDR_Writer)
