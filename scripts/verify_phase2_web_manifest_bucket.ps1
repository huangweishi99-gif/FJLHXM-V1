# Phase 2 Web manifest + local data pipeline bucket verification (no deploy).
param(
    [switch]$SkipSyncSmoke
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

Write-Host "=== manifest tests ===" -ForegroundColor Cyan
python -m pytest `
    tests/test_fengji_web_phase1_manifest.py `
    tests/test_fengji_api_phase1_manifest.py `
    tests/test_fengji_api_phase2_manifest.py `
    tests/test_fengji_api_phase3_manifest.py `
    tests/test_fengji_phase2_data_manifest.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "manifest pytest failed" }

Write-Host "=== Phase 2 data pipeline tests ===" -ForegroundColor Cyan
python -m pytest `
    tests/test_sync_domestic_futures_5m_for_context.py `
    tests/test_market_data_store_futures_local.py `
    -q
if ($LASTEXITCODE -ne 0) { throw "phase2 data pytest failed" }

if (-not $SkipSyncSmoke) {
    Write-Host "=== OpenAPI snapshot ===" -ForegroundColor Cyan
    $env:PYTHONPATH = "src;packages/fengji_core;services"
    python scripts/export_openapi_snapshot.py
    if ($LASTEXITCODE -ne 0) { throw "export_openapi_snapshot failed" }
}

Write-Host "=== Phase 2 Web manifest bucket OK ===" -ForegroundColor Green
