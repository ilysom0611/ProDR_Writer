@echo off
setlocal
rem Start the ProDR_Writer web UI in a minimized window.
rem
rem Default: serve the LAN - binds 0.0.0.0, prints this host's LAN URL, and
rem auto-generates an access token (persisted to .web-token) because any
rem non-loopback bind requires one (the UI can spend your stored LLM API key).
rem Loopback-only: set PRODR_HOST=127.0.0.1 before running.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo [ERROR] Not installed yet - run install.bat first. & exit /b 1)
if "%PRODR_PORT%"=="" set "PRODR_PORT=8000"
if "%PRODR_HOST%"=="" set "PRODR_HOST=0.0.0.0"

rem server.py derives its Host allowlist / token requirement from this env var,
rem so keep it in sync with the address uvicorn actually binds.
set "PRODR_WEB_HOST=%PRODR_HOST%"

rem Single-instance guard: refuse to start if the port is already listening.
netstat -ano | findstr /C:":%PRODR_PORT% " | findstr /I "LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [ERROR] Port %PRODR_PORT% is already in use - is ProDR_Writer already running? Use stop.bat first.
    exit /b 1
)

rem Detect the primary LAN address (display only - uvicorn binds PRODR_HOST).
set "LAN_IP="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "try { (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1).IPAddress } catch { '' }"`) do set "LAN_IP=%%i"
if "%LAN_IP%"=="" set "LAN_IP=<this-host>"

rem Non-loopback binds require a token; generate one on first start and reuse
rem it afterwards so the printed URL stays stable across restarts.
if "%PRODR_WEB_TOKEN%"=="" goto :load_token
goto :have_token
:load_token
if not exist .web-token goto :make_token
set /p PRODR_WEB_TOKEN=<.web-token
if not "%PRODR_WEB_TOKEN%"=="" goto :have_token
:make_token
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"`) do set "PRODR_WEB_TOKEN=%%t"
>.web-token echo %PRODR_WEB_TOKEN%
:have_token

start "ProDR_Writer" /min cmd /c ".venv\Scripts\python -m prodr_writer web --host "%PRODR_HOST%" --port "%PRODR_PORT%" ^> prodr-web.log 2^>^&1"
timeout /t 3 /nobreak >nul

rem Verify the process actually came up before claiming success.
netstat -ano | findstr /C:":%PRODR_PORT% " | findstr /I "LISTENING" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Failed to start - see prodr-web.log:
    type prodr-web.log
    exit /b 1
)
echo [OK] Started
echo   Local:   http://127.0.0.1:%PRODR_PORT%
echo   Network: http://%LAN_IP%:%PRODR_PORT%   ^(token: %PRODR_WEB_TOKEN%^)
echo   Log:     prodr-web.log, window title: ProDR_Writer
endlocal
