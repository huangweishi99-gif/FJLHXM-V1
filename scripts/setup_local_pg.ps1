# Local PostgreSQL + TimescaleDB (FJLHXM-V1)
# Usage: Docker Desktop Engine running, then:
#   powershell -ExecutionPolicy Bypass -File scripts/setup_local_pg.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Checking Docker..."
docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker not ready. Start Docker Desktop and retry." -ForegroundColor Red
    exit 1
}

Write-Host "==> Starting db container..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Waiting for PostgreSQL..."
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    docker compose exec -T db pg_isready -U fengji -d fengji 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "PostgreSQL timeout. Run: docker compose logs db" -ForegroundColor Red
    exit 1
}

Write-Host "==> Python deps (services/db)..."
pip install -q -r services/db/requirements.txt

Write-Host "==> Alembic upgrade head..."
alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Import CRYPTO CSV to PG..."
python scripts/import_crypto_csv_to_pg.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Import A_STOCK SQLite to PG..."
python scripts/migrate_sqlite_to_pg.py --market A_STOCK
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Done. DATABASE_URL=postgresql+psycopg://fengji:fengji_dev@localhost:5432/fengji" -ForegroundColor Green
