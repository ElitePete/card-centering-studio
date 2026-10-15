$ErrorActionPreference = "Stop"

$ProjectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$VirtualEnvironment = Join-Path $ProjectDirectory ".venv"
$PythonExecutable = Join-Path $VirtualEnvironment "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv $VirtualEnvironment
}

Write-Host "Installing application dependencies..."
& $PythonExecutable -m pip install --upgrade pip
& $PythonExecutable -m pip install -r (Join-Path $ProjectDirectory "requirements.txt")

Write-Host "Starting Card Centering Studio..."
& $PythonExecutable (Join-Path $ProjectDirectory "run_app.py")

