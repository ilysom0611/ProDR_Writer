@echo off
rem Update ProDR_Writer from git and restart
cd /d "%~dp0"
echo ==^> Pulling latest code
git pull --ff-only || (echo [ERROR] git pull failed. & exit /b 1)
echo ==^> Reinstalling package
.venv\Scripts\pip install -e . -q
echo [OK] Update complete. Restart with start.bat if it was running.
