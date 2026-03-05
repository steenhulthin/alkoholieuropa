param(
    [string]$InputDir = "data",
    [string]$OutputDir = "data/processed"
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $PSScriptRoot "data\.venv\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "data\transform_eurostat_xml_to_parquet.py"

if (-not (Test-Path $pythonExe)) {
    throw "Data venv interpreter not found: $pythonExe"
}

if (-not (Test-Path $scriptPath)) {
    throw "Transform script not found: $scriptPath"
}

& $pythonExe $scriptPath --input-dir $InputDir --output-dir $OutputDir
