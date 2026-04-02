# Proje kökünden: birim + Docker Postgres entegrasyon testleri
# Önkoşul: Docker Desktop açık, pip install -r requirements.txt

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/wait_for_postgres.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:CHRONICLE_INTEGRATION = "1"
python -m pytest tests/ -v --tb=short
exit $LASTEXITCODE
