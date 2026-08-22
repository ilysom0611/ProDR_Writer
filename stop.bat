@echo off
rem Stop the ProDR_Writer web UI
taskkill /FI "WINDOWTITLE eq ProDR_Writer*" /T >/dev/null 2>nul
if %errorlevel%==0 (echo [OK] Stopped.) else (echo Not running.^)
