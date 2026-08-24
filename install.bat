@echo off
setlocal
rem ProDR_Writer one-command installer (Windows).
rem
rem Works two ways:
rem   1. run standalone (downloaded alone): fetches the source first, then installs
rem   2. inside an existing checkout: installs in place
cd /d "%~dp0"


if exist pyproject.toml if exist src\prodr_writer goto :have_source

rem ---- Bootstrap: download the source into .\ProDR_Writer ----
set "PRODR_DEST=%~dp0ProDR_Writer"
echo ==^> Downloading ProDR_Writer into %PRODR_DEST%
where git >nul 2>nul
if not errorlevel 1 (
    git clone --depth 1 https://github.com/ilysom0611/ProDR_Writer.git "%PRODR_DEST%"
    if errorlevel 1 (
        echo [ERROR] git clone failed - check your network connection.
        exit /b 1
    )
    cd /d "%PRODR_DEST%"
    goto :have_source
)
where powershell >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Need either 'git' or PowerShell to download the source.
    exit /b 1
)
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://github.com/ilysom0611/ProDR_Writer/archive/refs/heads/main.zip' -OutFile 'ProDR_Writer-main.zip'; Expand-Archive -Path 'ProDR_Writer-main.zip' -DestinationPath '.' -Force; Move-Item -Force 'ProDR_Writer-main' '%PRODR_DEST%' } catch { exit 1 }"
if errorlevel 1 (
    echo [ERROR] Download failed - check your network connection.
    exit /b 1
)
del ProDR_Writer-main.zip >nul 2>nul
cd /d "%PRODR_DEST%"

:have_source

where python >nul 2>nul || (echo [ERROR] Python 3.10+ is required. Install from https://www.python.org/downloads/ & exit /b 1)

rem Reject the Windows Store python stub (it exists but only opens the Store)
python -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 'python' is not a working interpreter - this is usually the Windows Store stub.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    exit /b 1
)

rem Require Python 3.10 or newer
python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required. Your version:
    python --version
    exit /b 1
)

echo ==^> Creating virtual environment (.venv)
if exist .venv\Scripts\python.exe (
    echo      Reusing existing .venv
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
)

echo ==^> Installing ProDR_Writer and dependencies
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\pip install -e . -q
if errorlevel 1 (
    echo [ERROR] Installation failed.
    exit /b 1
)
echo.
echo [OK] Installation complete in %CD%
echo   Start:  start.bat    (web UI on this host's LAN address^)
echo   Stop:   stop.bat
echo   Update: update.bat
endlocal
