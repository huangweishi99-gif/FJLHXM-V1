# Sync N04 os_engine + rebuild scripts, then rebuild OS state on domestic/overseas servers.
param(
    [ValidateSet("domestic", "overseas", "both")]
    [string]$Target = "both",
    [switch]$SyncOnly,
    [switch]$SkipDomestic,
    [switch]$SkipOverseas
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-DomesticRebuild {
    Write-Host "`n=== DOMESTIC: sync core + rebuild OS state ===" -ForegroundColor Magenta
    & (Join-Path $Root "scripts/sync_deploy_domestic.ps1")
    if ($SyncOnly) { return }
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File 'C:/Users/Administrator/quant_futures/scripts/run_os_rebuild_n04_break_rule.ps1' -Profile domestic"
}

function Invoke-OverseasRebuild {
    Write-Host "`n=== OVERSEAS: sync core + rebuild OS state ===" -ForegroundColor Magenta
    & (Join-Path $Root "scripts/sync_deploy_overseas.ps1") -SkipSrc
    if ($SyncOnly) { return }
    ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && sed -i 's/\r$//' scripts/run_os_rebuild_n04_break_rule.sh && chmod +x scripts/run_os_rebuild_n04_break_rule.sh && bash scripts/run_os_rebuild_n04_break_rule.sh"
}

Write-Host "[local] verify os_engine N04 ..." -ForegroundColor Cyan
python scripts/verify_os_engine_n04.py
if ($LASTEXITCODE -ne 0) { throw "local os_engine N04 verification failed" }

if (($Target -eq "domestic" -or $Target -eq "both") -and -not $SkipDomestic) {
    Invoke-DomesticRebuild
}
if (($Target -eq "overseas" -or $Target -eq "both") -and -not $SkipOverseas) {
    Invoke-OverseasRebuild
}

Write-Host "`nN04 OS state rebuild orchestration done (target=$Target syncOnly=$SyncOnly)." -ForegroundColor Green
