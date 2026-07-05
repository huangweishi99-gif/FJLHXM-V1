# stash 运维桶：watchdog + data_manager 守卫 + PG/SC 15m 探针（最小 sync，不重启 radar/pending）
param(
    [switch]$InstallWatchdogTask
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

Write-Host "=== ops manifest test ===" -ForegroundColor Cyan
python -m pytest (Join-Path $root "tests\test_fengji_ops_domestic_manifest.py") -q
if ($LASTEXITCODE -ne 0) { throw "ops manifest pytest failed" }

& (Join-Path $root "scripts\sync_watchdog_domestic.ps1")
if ($LASTEXITCODE -ne 0) { throw "sync_watchdog_domestic failed" }

if ($InstallWatchdogTask) {
    Write-Host "=== install watchdog scheduled task (remote) ===" -ForegroundColor Cyan
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/install_watchdog_domestic_task.ps1"
}

Write-Host "=== Done ===" -ForegroundColor Green
