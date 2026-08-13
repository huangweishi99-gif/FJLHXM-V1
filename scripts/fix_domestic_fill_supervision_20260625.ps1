# Fix domestic fill_supervision watchdog: EG DS03 watch stale + deploy execution/supervision patch
param(
    [string]$DomesticHost = "domestic-quant",
    [string]$DomesticRoot = "C:/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$py = "python"

Write-Host "=== Local tests ===" -ForegroundColor Cyan
& $py -m pytest tests/test_ds03_pending_fill.py tests/test_fill_supervision.py -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "=== Merge ack (local base from remote) ===" -ForegroundColor Cyan
$remoteAck = Join-Path $root "runtime/fill_supervision_acknowledged_remote.json"
$localAck = Join-Path $root "runtime/fill_supervision_acknowledged.json"
if (Test-Path $remoteAck) {
    Copy-Item -Force $remoteAck $localAck
}
& $py scripts/register_domestic_fill_invalid_ack_20260625.py
if ($LASTEXITCODE -ne 0) { throw "ack register failed" }

$files = @(
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py",
    "src/fengji_futures_pending_order_monitor.py",
    "scripts/watchdog_domestic.ps1"
)
foreach ($rel in $files) {
    $local = Join-Path $root ($rel -replace "/", "\")
    $remote = "$DomesticRoot/$($rel -replace '\\','/')"
    scp -o BatchMode=yes -o ConnectTimeout=25 $local "${DomesticHost}:$remote"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
    Write-Host "synced: $rel"
}

scp -o BatchMode=yes -o ConnectTimeout=25 $localAck "${DomesticHost}:$DomesticRoot/runtime/fill_supervision_acknowledged.json"
if ($LASTEXITCODE -ne 0) { throw "scp ack failed" }
Write-Host "synced: fill_supervision_acknowledged.json"

Write-Host "=== Remote verify 72h audit ===" -ForegroundColor Cyan
$remotePy = "C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe"
ssh -o BatchMode=yes -o ConnectTimeout=30 $DomesticHost @"
powershell -NoProfile -ExecutionPolicy Bypass -Command "
  Set-Location '$DomesticRoot';
  `$env:PYTHONPATH='src;packages/fengji_core';
  `$env:FENGJI_MARKET='futures';
  & '$remotePy' scripts/audit_paper_fills.py --root '$DomesticRoot' --profile domestic --since-hours 72 --fail-on-invalid --ack-file runtime/fill_supervision_acknowledged.json --quiet;
  Write-Output ('FILL_AUDIT_EXIT=' + `$LASTEXITCODE);
  Remove-Item runtime/watchdog/fill_supervision_invalid.alert -ErrorAction SilentlyContinue;
  & powershell -NoProfile -ExecutionPolicy Bypass -File scripts/watchdog_domestic.ps1 | Select-Object -Last 8
"
"@

Write-Host "=== Done ===" -ForegroundColor Green
