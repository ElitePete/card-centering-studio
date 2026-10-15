@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHONW%" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%install_and_run.ps1"
    exit /b %ERRORLEVEL%
)

"%PYTHON%" -c "import PySide6, cv2, PIL" >nul 2>&1
if errorlevel 1 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%install_and_run.ps1"
    exit /b %ERRORLEVEL%
)

start "Card Centering Studio" "%PYTHONW%" "%PROJECT_DIR%run_app.py"

