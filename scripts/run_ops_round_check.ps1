param(
    [string]$RoundTag = "",
    [switch]$SyncHashesOnMismatch
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if (-not $RoundTag) {
    $RoundTag = "r{0}" -f (Get-Date -Format "HHmm")
}
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "results\ops_round_${stamp}_$RoundTag"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

python (Join-Path $root "scripts\ops_round_r8_remote_checks.py") 2>&1 | Out-File -Encoding utf8 (Join-Path $root "runtime\ops_latest_check.json")
Copy-Item (Join-Path $root "runtime\ops_latest_check.json") (Join-Path $outDir "remote_checks.json") -Force

$hashRc = 0
python (Join-Path $root "scripts\compare_overseas_core_hashes.py") 2>&1 | Tee-Object -FilePath (Join-Path $outDir "core_hash_compare.json")
$hashRc = $LASTEXITCODE
if ($SyncHashesOnMismatch -and $hashRc -ne 0) {
    & (Join-Path $root "scripts\sync_overseas_core_hash_files.ps1")
}

python (Join-Path $root "scripts\compare_domestic_ds08_hashes.py") 2>&1 | Tee-Object -FilePath (Join-Path $outDir "domestic_ds08_hash_compare.json")

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\sync_overseas_paper_state.ps1") 2>&1 | Out-Null
python (Join-Path $root "scripts\promote_overseas_1d_new10.py") 2>&1 | Out-File -Encoding utf8 (Join-Path $outDir "promote_overseas_1d.json")
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\sync_overseas_crypto_15m_for_followup.ps1") 2>&1 | Out-File -Encoding utf8 (Join-Path $outDir "sync_overseas_15m.json")
python (Join-Path $root "scripts\sync_new10_open_intraday.py") 2>&1 | Out-File -Encoding utf8 (Join-Path $outDir "sync_new10_intraday.json")

$env:FENGJI_NEW10_WATCH_QUIET = "1"
$env:PYTHONPATH = "scripts;src;packages/fengji_core;services"
python (Join-Path $root "scripts\watch_new10_crypto_fills.py") 2>&1 | Tee-Object -FilePath (Join-Path $outDir "new10_watch.json")

$domesticScan = Join-Path $outDir "domestic_futures_scan.json"
python (Join-Path $root "scripts\scan_domestic_futures_fills.py") --hours 336 --out $domesticScan 2>&1 | Out-Null

python (Join-Path $root "scripts\validate_crypto_okx_180d_cache.py") 2>&1 | Tee-Object -FilePath (Join-Path $outDir "crypto_180d_cache_guard.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "crypto 180d cache guard failed; check data/crypto_okx before heavy backtests"
}

$followupDir = Join-Path $outDir "new10_open_followup"
python (Join-Path $root "scripts\report_new10_open_followup.py") --out-dir $followupDir 2>&1 | Out-Null

python (Join-Path $root "scripts\watch_hype28_stop.py") --json 2>&1 | Tee-Object -FilePath (Join-Path $outDir "hype28_stop_watch.json")

$closesDir = Join-Path $outDir "new10_recent_closes"
python (Join-Path $root "scripts\report_new10_recent_closes.py") --since "2026-06-28 00:00:00" --out-dir $closesDir 2>&1 | Out-Null

python -m pytest (Join-Path $root "tests\test_os_engine.py") (Join-Path $root "tests\test_ds01.py") (Join-Path $root "tests\test_pending_orders.py") (Join-Path $root "tests\test_fill_supervision.py") (Join-Path $root "tests\test_sync_okx_crypto_timeframes.py") (Join-Path $root "tests\test_feishu_notify.py") (Join-Path $root "tests\test_radar_ds09.py") (Join-Path $root "tests\test_check_ds09_feishu_dedup_state.py") (Join-Path $root "tests\test_report_new10_open_followup.py") (Join-Path $root "tests\test_stop_bar_monitor.py") (Join-Path $root "tests\test_sync_new10_open_intraday.py") (Join-Path $root "tests\test_data_manager_futures_main_contracts.py") (Join-Path $root "tests\test_market_data_resolve.py") (Join-Path $root "tests\test_validate_crypto_okx_180d_cache.py") -q 2>&1 | Tee-Object -FilePath (Join-Path $outDir "pytest.txt")

Write-Host "ops_round=$outDir"
exit 0
