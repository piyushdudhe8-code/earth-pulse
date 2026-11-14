$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Use the Python installation available on PATH.
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    throw "Python was not found on PATH. Check: python --version"
}

$pythonExe = $pythonCommand.Source
$pythonVersion = & $pythonExe --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Python could not be started. Check your Python installation."
}
Write-Host ("Using " + $pythonVersion) -ForegroundColor Cyan

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $pythonExe -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the virtual environment."
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment Python was not created."
}

Write-Host "Installing project dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not upgrade pip. Check your internet connection and try again."
}

& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Dependency installation failed. Read the pip error above."
}

Write-Host "Launching EARTH PULSE..." -ForegroundColor Green
& $venvPython -m streamlit run (Join-Path $PSScriptRoot "app.py")
exit $LASTEXITCODE
