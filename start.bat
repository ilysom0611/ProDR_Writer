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

rem Single-instance guard: refuse to start if a live ProDR_Writer python
rem process is recorded in .web.pid (written below once the server is up).
if not exist .web.pid goto :no_pidfile
set /p OLD_PID=<.web.pid 2>nul
echo %OLD_PID%| findstr /R "^[0-9][0-9]*$" >nul 2>nul
if errorlevel 1 goto :stale_pid
tasklist /FI "PID eq %OLD_PID%" 2>nul | findstr /I /B /C:"python" >nul 2>nul
if errorlevel 1 goto :stale_pid
echo Already running ^(PID %OLD_PID%^). Use stop.bat first.
exit /b 0

:stale_pid
echo Replacing stale .web.pid ^(PID %OLD_PID% is not ProDR_Writer^).
del .web.pid >nul 2>nul
:no_pidfile

rem Backstop guard: the port itself is busy (e.g. another app or a server this
rem pidfile never knew about).
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
rem Loopback-only binds (localhost / 127.x / ::1) need none - mirror start.sh.
set "IS_LOOPBACK="
if /I "%PRODR_HOST%"=="localhost" set "IS_LOOPBACK=1"
if "%PRODR_HOST%"=="::1" set "IS_LOOPBACK=1"
if defined IS_LOOPBACK goto :have_token
echo %PRODR_HOST%| findstr /B /C:"127." >nul 2>nul
if not errorlevel 1 goto :have_token

if not "%PRODR_WEB_TOKEN%"=="" goto :have_token
if not exist .web-token goto :make_token
set /p PRODR_WEB_TOKEN=<.web-token
if not "%PRODR_WEB_TOKEN%"=="" goto :have_token
:make_token
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"`) do set "PRODR_WEB_TOKEN=%%t"
>.web-token echo %PRODR_WEB_TOKEN%
:have_token

rem Launch detached via Start-Process: a hidden window (no console title to
rem match on stop), stdout+stderr into prodr-web.log, immune to the nested
rem quoting that broke `start ... cmd /c` invocations.
powershell -NoProfile -Command "$p = Start-Process -WindowStyle Hidden -FilePath '.venv\Scripts\python.exe' -ArgumentList '-m','prodr_writer','web','--host','%PRODR_HOST%','--port','%PRODR_PORT%' -RedirectStandardOutput 'prodr-web.log' -RedirectStandardError 'prodr-web.err.log' -PassThru; exit 0"
if errorlevel 1 (
    echo [ERROR] Could not launch the server process.
    exit /b 1
)

rem Poll for readiness (up to ~20s) instead of a fixed sleep - slow starts,
rem cold caches or antivirus scans must not be declared failed while the
rem server is still coming up.
set /a TRIES=0
:wait_ready
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $w=$c.BeginConnect('127.0.0.1',%PRODR_PORT%,$null,$null); if ($w.AsyncWaitHandle.WaitOne(500) -and $c.Connected) { exit 0 } else { exit 1 } } catch { exit 1 } finally { $c.Close() }" >nul 2>nul
if not errorlevel 1 goto :port_up
set /a TRIES+=1
if %TRIES% geq 20 (
    echo [ERROR] Failed to start - see prodr-web.log:
    type prodr-web.log 2>nul
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto :wait_ready

rem Record the PID of whoever is now listening so stop.bat can target it.
:port_up
set "WEB_PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":%PRODR_PORT% " ^| findstr /I "LISTENING"') do set "WEB_PID=%%p"
tasklist /FI "PID eq %WEB_PID%" 2>nul | findstr /I /B /C:"python" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Port %PRODR_PORT% came up but is not held by a python process - see prodr-web.log:
    type prodr-web.log 2>nul
    exit /b 1
)
>.web.pid echo %WEB_PID%
echo [OK] Started ^(PID %WEB_PID%^)
echo   Local:   http://127.0.0.1:%PRODR_PORT%
if defined PRODR_WEB_TOKEN (
    echo   Network: http://%LAN_IP%:%PRODR_PORT%   ^(token: %PRODR_WEB_TOKEN%^)
) else (
    echo   Network: http://%LAN_IP%:%PRODR_PORT%
)
echo   Log:     prodr-web.log
endlocal
