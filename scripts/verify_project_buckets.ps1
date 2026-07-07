# Run local manifest bucket verifications (Phase 2 data + archive docs).
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

Write-Host "=== Phase 2 Web/data manifest ===" -ForegroundColor Cyan
powershell -NoProfile -File (Join-Path $root "scripts\verify_phase2_web_manifest_bucket.ps1")
if ($LASTEXITCODE -ne 0) { throw "phase2 bucket failed" }

Write-Host "`n=== Archive docs manifest ===" -ForegroundColor Cyan
powershell -NoProfile -File (Join-Path $root "scripts\verify_archive_docs_bucket.ps1")
if ($LASTEXITCODE -ne 0) { throw "archive bucket failed" }

Write-Host "`n=== Domestic ops manifest ===" -ForegroundColor Cyan
python -m pytest (Join-Path $root "tests\test_fengji_ops_domestic_manifest.py") -q
if ($LASTEXITCODE -ne 0) { throw "ops manifest pytest failed" }

Write-Host "`n=== Domestic deploy manifest ===" -ForegroundColor Cyan
python -m pytest (Join-Path $root "tests\test_fengji_domestic_deploy_manifest.py") -q
if ($LASTEXITCODE -ne 0) { throw "domestic deploy manifest pytest failed" }

Write-Host "`n=== Phase 2 closeout manifest ===" -ForegroundColor Cyan
python -m pytest (Join-Path $root "tests\test_phase2_closeout_manifest.py") -q
if ($LASTEXITCODE -ne 0) { throw "phase2 closeout manifest pytest failed" }

Write-Host "`n=== All project buckets OK ===" -ForegroundColor Green
