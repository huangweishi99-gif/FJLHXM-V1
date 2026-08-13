param(
    [string]$DataDir = "",
    [string]$OutDir = "",
    [int]$LookbackDays = 120
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if (-not $DataDir) { $DataDir = Join-Path $root "data" }
if (-not $OutDir) {
    $stamp = Get-Date -Format "yyyyMMdd"
    $OutDir = Join-Path $root "results\crypto_camp_sandbox_review_$stamp"
}

$env:PYTHONPATH = "scripts;src;packages/fengji_core;services"

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\sync_overseas_crypto_1d_for_audit.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python (Join-Path $root "scripts\audit_crypto_camp_snapshot.py") `
    --data-dir $DataDir `
    --out (Join-Path (Split-Path $OutDir) "crypto_camp_snapshot_$(Get-Date -Format yyyyMMdd)\report.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python (Join-Path $root "scripts\audit_crypto_camp_sandbox_review.py") `
    --data-dir $DataDir `
    --lookback-days $LookbackDays `
    --out-dir $OutDir
exit $LASTEXITCODE
