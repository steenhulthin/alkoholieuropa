param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $PSScriptRoot "alcoholandsex\.venv\Scripts\python.exe"
$appPath = Join-Path $PSScriptRoot "alcoholandsex\app.py"

if (-not (Test-Path $pythonExe)) {
    throw "App venv interpreter not found: $pythonExe"
}

if (-not (Test-Path $appPath)) {
    throw "Shiny app not found: $appPath"
}

& $pythonExe -m shiny run --reload --port $Port $appPath
