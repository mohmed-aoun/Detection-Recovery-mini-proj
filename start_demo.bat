@echo off
REM Detection & Recovery — Windows launcher
REM Usage: Double-click run.bat  OR  run it from a terminal

setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
REM Strip trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "VENV=%PROJECT_DIR%\venv\Scripts\activate.bat"
set "PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"
set "DASHBOARD=%PROJECT_DIR%\dashboard.html"

echo.
echo  +-- Detection ^& Recovery (Windows) ---------------------------+
echo  ^|  Setting up environment...                                  ^|
echo  +--------------------------------------------------------------+
echo.

REM -- Preflight: python -------------------------------------------------------

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download it from https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

REM -- Setup venv + dependencies -----------------------------------------------

if not exist "%VENV%" (
    echo [INFO] Creating virtual environment...
    python -m venv "%PROJECT_DIR%\venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call "%VENV%"

echo [INFO] Installing dependencies...
pip install -q -r "%PROJECT_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

REM -- Write temp launcher scripts (safe against spaces in path) ---------------

set "TMP_DIR=%PROJECT_DIR%\venv\tmp_launchers"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

(
    echo @echo off
    echo cd /d "%PROJECT_DIR%"
    echo call "%VENV%"
    echo python primary_server.py
    echo pause
) > "%TMP_DIR%\run_primary.bat"

(
    echo @echo off
    echo cd /d "%PROJECT_DIR%"
    echo call "%VENV%"
    echo python backup_server.py
    echo pause
) > "%TMP_DIR%\run_backup.bat"

(
    echo @echo off
    echo cd /d "%PROJECT_DIR%"
    echo call "%VENV%"
    echo python client_server.py
    echo pause
) > "%TMP_DIR%\run_client.bat"

REM -- Launch the three servers in separate windows ----------------------------

echo [INFO] Starting primary_server.py  (port 5000)...
start "Primary Server :5000" cmd /k "%TMP_DIR%\run_primary.bat"

echo [INFO] Starting backup_server.py   (port 5001)...
start "Backup Server :5001"  cmd /k "%TMP_DIR%\run_backup.bat"

REM Give the servers a 2-second head-start (mirrors sleep 2 in run.sh)
echo [INFO] Waiting 2 seconds before starting client...
timeout /t 2 /nobreak >nul

echo [INFO] Starting client_server.py   (port 5002)...
start "Client Server :5002"  cmd /k "%TMP_DIR%\run_client.bat"

REM -- Open dashboard in default browser --------------------------------------

echo [INFO] Opening dashboard...
start "" "%DASHBOARD%"

REM -- Summary ----------------------------------------------------------------

echo.
echo  +--------------------------------------------------------------+
echo  ^|  Primary server  ^> http://localhost:5000                    ^|
echo  ^|  Backup server   ^> http://localhost:5001                    ^|
echo  ^|  Client server   ^> http://localhost:5002                    ^|
echo  ^|                                                              ^|
echo  ^|  Dashboard opened in your default browser.                  ^|
echo  ^|  Close the individual server windows to stop them.          ^|
echo  +--------------------------------------------------------------+
echo.

pause