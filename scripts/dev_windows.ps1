# SYNTHETIC LOCAL DEMO ONLY. Do not place real patient data here.
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".venv/Scripts/python.exe")) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Provide Python 3.11+ with -Python <path-to-python.exe>" }
}
& .\.venv\Scripts\python.exe -m pip install -c backend/constraints-baseline.txt -e ".\backend[dev]"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed; demo was not started" }
$env:DENLYRA_DEMO_MODE = "1"
$env:DENLYRA_DATABASE_URL = "sqlite+pysqlite:///./local_data/denlyra-demo.db"
& .\.venv\Scripts\python.exe -m denlyra
