# VeriAI Setup Script
Write-Host "Setting up VeriAI..." -ForegroundColor Cyan

# Check if virtual environment exists
if (Test-Path ".\env") {
    Write-Host "Virtual environment already exists. Activating..." -ForegroundColor Yellow
} else {
    Write-Host "Creating virtual environment..." -ForegroundColor Green
    python -m venv env
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
.\env\Scripts\Activate.ps1

# Install requirements
Write-Host "Installing dependencies..." -ForegroundColor Green
pip install --upgrade pip
pip install -r requirements.txt

Write-Host "`nSetup complete! Run '.\run.ps1' to start the application." -ForegroundColor Cyan
