# Quick domestic futures main-contract + runtime health check (local manifest or remote SSH).
param(
    [switch]$Remote
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if ($Remote) {
    Write-Host "=== remote manifest audit ===" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "verify_domestic_futures_main_contract.ps1")
    Write-Host "=== remote processes ===" -ForegroundColor Cyan
    $ps = @'
$r = "C:/Users/Administrator/quant_futures"
. "$r/scripts/resolve_domestic_paper.ps1"
$paper = Get-DomesticPaperScript -Root $r
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  $c = $_.CommandLine
  if (-not $c) { return }
  if ($c -match 'data_manager_futures') { "data_manager=$($_.ProcessId)" }
  elseif ($c -match 'fengji_futures_pending_order_monitor') { "pending=$($_.ProcessId)" }
  elseif ($c -match [regex]::Escape($paper)) { "paper=$($_.ProcessId)" }
}
Set-Location $r
$env:PYTHONPATH = 'src;packages/fengji_core'
& python -c "import fengji_core.futures_main_contract as m; print('lookup_LH', m.lookup_data_contract('LH'))"
'@
    $ps | ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -Command -"
    exit 0
}

$manifest = Join-Path $root "runtime\domestic_futures_main_contract_sources.json"
if (-not (Test-Path $manifest)) {
    $manifest = Join-Path $root "runtime\logs\futures_main_contract_sources.json"
}
if (-not (Test-Path $manifest)) {
    Write-Host "WARN no local manifest; use -Remote for server audit" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== local manifest audit ===" -ForegroundColor Cyan
python scripts\verify_futures_main_contract_manifest.py --manifest $manifest
Write-Host "=== import smoke ===" -ForegroundColor Cyan
$env:PYTHONPATH = "src;packages/fengji_core"
$env:FUTURES_MAIN_CONTRACT_MANIFEST = $manifest
python -c "from fengji_core.futures_main_contract import lookup_data_contract; print('lookup_LH', lookup_data_contract('LH'))"
