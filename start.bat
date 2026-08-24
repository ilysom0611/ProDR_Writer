@echo off
setlocal
rem Start the ProDR_Writer web UI in a minimized window
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo [ERROR] Not installed yet - run install.bat first. & exit /b 1)
if "%PRODR_PORT%"=="" set "PRODR_PORT=8000"
if "%PRODR_HOST%"=="" set "PRODR_HOST=127.0.0.1"

rem server.py derives its Host allowlist / token requirement from this env var,
rem so keep it in sync with the address uvicorn actually binds.
set "PRODR_WEB_HOST=%PRODR_HOST%"

rem Single-instance guard: refuse to start if the port is already listening.
netstat -ano | findstr /C:":%PRODR_PORT% " | findstr /I "LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [ERROR] Port %PRODR_PORT% is already in use - is ProDR_Writer already running? Use stop.bat first.
    exit /b 1
)

start "ProDR_Writer" /min cmd /c ".venv\Scripts\python -m prodr_writer web --host "%PRODR_HOST%" --port "%PRODR_PORT%" ^> prodr-web.log 2^>^&1"
timeout /t 3 /nobreak >nul

rem Verify the process actually came up before claiming success.
netstat -ano | findstr /C:":%PRODR_PORT% " | findstr /I "LISTENING" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Failed to start - see prodr-web.log:
    type prodr-web.log
    exit /b 1
)
echo [OK] Started: http://%PRODR_HOST%:%PRODR_PORT%  (log: prodr-web.log, window title: ProDR_Writer)
endlocal
