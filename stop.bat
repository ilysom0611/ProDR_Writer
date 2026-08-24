@echo off
setlocal EnableDelayedExpansion
rem Stop the ProDR_Writer web UI.
rem
rem Order: trust .web.pid (written by start.bat) if it points at a live
rem python.exe; otherwise fall back to whatever is LISTENING on %PRODR_PORT%.
rem Nothing is killed until it has been verified to look like ours. Always
rem exits 0 so callers such as update.bat are not tripped up by "nothing ran".
cd /d "%~dp0"
if "%PRODR_PORT%"=="" set "PRODR_PORT=8000"

set "STOPPED=0"

if not exist .web.pid goto :fallback
set /p STOP_PID=<.web.pid 2>nul
rem The pidfile must contain a plain number - anything else is corrupt.
echo !STOP_PID!| findstr /R "^[0-9][0-9]*$" >nul 2>nul
if errorlevel 1 (
    echo Ignoring malformed .web.pid.
    del .web.pid >nul 2>nul
    goto :fallback
)
call :is_ours !STOP_PID!
if errorlevel 1 (
    echo Ignoring stale .web.pid ^(PID !STOP_PID! is not ProDR_Writer^).
    del .web.pid >nul 2>nul
    goto :fallback
)
taskkill /PID !STOP_PID! /T /F >nul 2>nul
call :wait_gone !STOP_PID!
del .web.pid >nul 2>nul
echo [OK] Stopped ^(PID !STOP_PID!^)
set "STOPPED=1"
goto :done

:fallback
rem No usable pidfile: find the listener on the port and verify it is python
rem before killing, so an unrelated process is never terminated.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":%PRODR_PORT% " ^| findstr /I "LISTENING"') do (
    call :is_ours %%p
    if not errorlevel 1 (
        taskkill /PID %%p /T /F >nul 2>nul
        call :wait_gone %%p
        echo [OK] Stopped ^(PID %%p, found listening on port %PRODR_PORT%^)
        set "STOPPED=1"
    )
)

:done
if "%STOPPED%"=="0" echo Not running.
endlocal
exit /b 0

:is_ours
rem %1 = PID. Returns 0 only if that PID exists and its image is python*.exe.
tasklist /FI "PID eq %~1" 2>nul | findstr /I /B /C:"python" >nul 2>nul
exit /b %errorlevel%

:wait_gone
rem Briefly wait for the process to disappear so a following start.bat does
rem not lose the race for the port.
set /a WG_N=0
:wait_gone_loop
call :is_ours %~1 || exit /b 0
set /a WG_N+=1
if %WG_N% geq 10 exit /b 0
ping -n 2 127.0.0.1 >nul
goto :wait_gone_loop
