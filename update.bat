@echo off
setlocal
rem Update ProDR_Writer from git and restart only if it was running.
rem
rem Order matters: the pull happens BEFORE stopping anything, so a failed pull
rem (local changes, network down) never leaves a previously running service down.
cd /d "%~dp0"
if not exist .venv\Scripts\pip.exe (echo [ERROR] Not installed yet - run install.bat first. & exit /b 1)

rem Remember whether the service is currently running - decided before anything
rem is touched, based on a live python process recorded in .web.pid.
set "WAS_RUNNING=0"
if not exist .web.pid goto :pull
set /p UPD_PID=<.web.pid 2>nul
echo %UPD_PID%| findstr /R "^[0-9][0-9]*$" >nul 2>nul
if errorlevel 1 goto :pull
tasklist /FI "PID eq %UPD_PID%" 2>nul | findstr /I /B /C:"python" >nul 2>nul
if errorlevel 1 goto :pull
set "WAS_RUNNING=1"

:pull
echo ==^> Pulling latest code
git pull --ff-only
if errorlevel 1 (
    echo.
    echo [ERROR] git pull failed - your checkout has local changes or cannot reach origin.
    echo         Nothing was stopped or modified. Resolve with 'git stash' or commit,
    echo         then re-run update.bat
    exit /b 1
)

echo ==^> Reinstalling package
.venv\Scripts\pip install -e . -q
if errorlevel 1 (
    echo [ERROR] Installation failed.
    exit /b 1
)

if "%WAS_RUNNING%"=="0" goto :not_running

echo ==^> Restarting updated instance
rem ".\" prefix: resolve from the script directory even under environments
rem that exclude the current directory from executable lookup.
call .\stop.bat
call .\start.bat
endlocal
exit /b 0

:not_running
echo [OK] Update complete. Start with start.bat
endlocal
