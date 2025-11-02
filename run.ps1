param(
  [string]$Python="python"
)
$ErrorActionPreference = "Stop"

# Support both .venv and env directories
$venvDir = if (Test-Path ".venv") { ".venv" } elseif (Test-Path "env") { "env" } else { ".venv" }

if (!(Test-Path $venvDir)) {
  Write-Host "Creating virtual environment..." -ForegroundColor Green
  & $Python -m venv $venvDir
}

Write-Host "Activating virtual environment..." -ForegroundColor Green
. "$venvDir/Scripts/Activate.ps1"

Write-Host "Installing/updating dependencies..." -ForegroundColor Green
& python -m pip install -U pip
& python -m pip install -r requirements.txt

Write-Host "Starting VeriAI..." -ForegroundColor Cyan
& python backend/vri.py
