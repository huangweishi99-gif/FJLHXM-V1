# Deploy domestic futures main-contract silent rollover audit + entry_data_contract stamping
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$remote = "C:/Users/Administrator/quant_futures"

$files = @(
    "data_manager_futures.py",
    "packages/fengji_core/fengji_core/futures_main_contract.py",
    "src/fengji_futures_pending_order_monitor.py",
    "services/monitor_domestic.py"
)

foreach ($rel in $files) {
    $local = Join-Path $root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
    $dest = "$remote/$($rel -replace '\\','/')"
    $destDir = ($dest -replace '/[^/]+$', '')
    ssh -o BatchMode=yes domestic-quant "if (-not (Test-Path '$destDir')) { New-Item -ItemType Directory -Force -Path '$destDir' | Out-Null }"
    scp -o BatchMode=yes -o ConnectTimeout=30 $local "domestic-quant:$dest"
    Write-Host "synced: $rel"
}

& (Join-Path $PSScriptRoot "deploy_domestic_paper_feishu.ps1")

Write-Host "=== restart data_manager (minimal) ===" -ForegroundColor Cyan
scp -o BatchMode=yes scripts/restart_domestic_data_manager.ps1 domestic-quant:$remote/scripts/
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File $remote/scripts/restart_domestic_data_manager.ps1"

Write-Host "=== restart pending + paper via watchdog ===" -ForegroundColor Cyan
scp -o BatchMode=yes scripts/restart_domestic_pending_monitor.ps1 domestic-quant:$remote/scripts/
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File $remote/scripts/restart_domestic_pending_monitor.ps1"
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File $remote/scripts/watchdog_domestic.ps1" | Select-Object -Last 15

Write-Host "=== verify import ===" -ForegroundColor Cyan
$verify = @'
$r = 'C:/Users/Administrator/quant_futures'
Set-Location $r
$env:PYTHONPATH = 'src;packages/fengji_core'
& python -c "import fengji_core.futures_main_contract as m; import data_manager_futures as dm; print('ok', bool(m.lookup_data_contract('LH')))"
'@
$verify | ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -Command -"

Write-Host "=== Done ===" -ForegroundColor Green
