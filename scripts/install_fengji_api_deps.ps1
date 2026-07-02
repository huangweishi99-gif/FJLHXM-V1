# Install FengJi Web API Python deps on the deploy host (W17-prod).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$apiReq = Join-Path $Root "services\api\requirements.txt"
$dbReq = Join-Path $Root "services\db\requirements.txt"
if (-not (Test-Path -LiteralPath $apiReq)) {
    throw "Missing $apiReq — sync manifest first"
}
if (-not (Test-Path -LiteralPath $dbReq)) {
    throw "Missing $dbReq — sync manifest first"
}

Write-Host "Installing API requirements ..." -ForegroundColor Cyan
python -m pip install -r $apiReq
python -m pip install -r $dbReq
python -m pip show alembic psycopg fastapi uvicorn | Select-String "Name:|Version:"
Write-Host "FengJi API deps OK" -ForegroundColor Green
