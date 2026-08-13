# 海外 crypto 数据泵 hash 对齐：data_manager.py + crypto_ingest.py
param(
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$files = @(
    "data_manager.py",
    "services/crypto_ingest.py",
    "scripts/sync_missing_crypto_15m.py"
)

Write-Host "=== pytest ===" -ForegroundColor Cyan
python -m pytest (Join-Path $root "tests\test_sync_okx_crypto_timeframes.py") (Join-Path $root "tests\test_validate_crypto_okx_180d_cache.py") -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

$remoteRoot = "/home/ubuntu/quant_crypto"
foreach ($rel in $files) {
    $local = Join-Path $root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
    $remote = "$remoteRoot/$($rel -replace '\\','/')"
    scp -o BatchMode=yes -o ConnectTimeout=25 $local "overseas-quant:$remote"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
    Write-Host "synced overseas: $rel"
}

if (-not $NoRestart) {
    ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && pkill -f 'data_manager.py' 2>/dev/null || true; bash scripts/watchdog_overseas.sh 2>&1 | tail -6"
}

Write-Host "=== hash check ===" -ForegroundColor Cyan
python (Join-Path $root "scripts\compare_overseas_core_hashes.py")
if ($LASTEXITCODE -ne 0) { Write-Warning "compare_overseas_core_hashes reported mismatches (see JSON above)" }

Write-Host "=== Done ===" -ForegroundColor Green
