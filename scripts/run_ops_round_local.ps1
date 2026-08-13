param(
    [int]$Round = 0,
    [switch]$EmitSandbox
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if ($Round -le 0) {
    $Round = [int](Get-Date -Format "HH")
}
$stamp = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $root "results\ops_round_${stamp}_r$Round"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$env:PYTHONPATH = "scripts;src;packages/fengji_core;services"

python (Join-Path $root "scripts\ops_round_r8_remote_checks.py") 2>&1 |
    Out-File -Encoding utf8 (Join-Path $root "runtime\ops_latest_check.json")
Copy-Item (Join-Path $root "runtime\ops_latest_check.json") (Join-Path $outDir "remote_checks.json") -Force

python (Join-Path $root "scripts\compare_overseas_core_hashes.py") 2>&1 |
    Out-File -Encoding utf8 (Join-Path $outDir "core_hash_compare.json")

$env:FENGJI_SYNC_QUIET = "1"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\sync_overseas_paper_state.ps1") | Out-Null

$env:FENGJI_NEW10_WATCH_QUIET = "1"
$watchArgs = @(Join-Path $root "scripts\watch_new10_crypto_fills.py")
if ($EmitSandbox) { $watchArgs += "--emit-sandbox" }
python @watchArgs 2>&1 | Out-File -Encoding utf8 (Join-Path $outDir "new10_watch.json")

python -m pytest (Join-Path $root "tests\test_os_engine.py") `
    (Join-Path $root "tests\test_ds01.py") `
    (Join-Path $root "tests\test_pending_orders.py") `
    (Join-Path $root "tests\test_data_manager_futures_main_contracts.py") -q 2>&1 |
    Tee-Object -FilePath (Join-Path $outDir "pytest.txt")

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\check_domestic_tq_env.ps1") 2>&1 |
    Out-File -Encoding utf8 (Join-Path $outDir "domestic_tq_env.txt")

Write-Host "ops_round saved: $outDir"
exit $LASTEXITCODE
