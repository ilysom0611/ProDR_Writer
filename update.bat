@echo off
setlocal
rem Update ProDR_Writer from git and restart
cd /d "%~dp0"
if not exist .venv\Scripts\pip.exe (echo [ERROR] Not installed yet - run install.bat first. & exit /b 1)

echo ==^> Stopping running instance (if any)
call stop.bat

echo ==^> Pulling latest code
git pull --ff-only || (echo [ERROR] git pull failed. & exit /b 1)
echo ==^> Reinstalling package
.venv\Scripts\pip install -e . -q
if errorlevel 1 (
    echo [ERROR] Installation failed.
    exit /b 1
)
echo [OK] Update complete.
choice /M "Restart the web UI now"
if "%errorlevel%"=="1" call start.bat
endlocal
