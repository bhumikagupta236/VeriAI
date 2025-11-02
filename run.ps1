param(
  [string]$Python="python"
)
$ErrorActionPreference = "Stop"
$venvDir = ".venv"
if (!(Test-Path $venvDir)) {
  & $Python -m venv $venvDir
}
. "$venvDir/Scripts/Activate.ps1"
& python -m pip install -U pip
& python -m pip install -r requirements.txt
& python backend/vri.py
