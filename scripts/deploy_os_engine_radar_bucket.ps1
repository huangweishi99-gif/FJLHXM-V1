# os_engine + total_radar + DS07 桶（stash cherry-pick 后同步）
param(
    [switch]$OverseasOnly,
    [switch]$DomesticOnly,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$files = @(
    "packages/fengji_core/fengji_core/os_engine.py",
    "packages/fengji_core/fengji_core/ds07.py",
    "src/fengji_total_radar.py"
)

function Sync-List([string]$HostAlias, [string]$RemoteRoot, [string[]]$Paths) {
    foreach ($rel in $Paths) {
        $local = Join-Path $root ($rel -replace "/", "\")
        if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
        $remote = "$RemoteRoot/$($rel -replace '\\','/')"
        scp -o BatchMode=yes -o ConnectTimeout=25 $local "${HostAlias}:$remote"
        if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
        Write-Host "synced ${HostAlias}: $rel"
    }
}

if (-not $DomesticOnly) {
    Write-Host "=== Overseas ===" -ForegroundColor Cyan
    Sync-List "overseas-quant" "/home/ubuntu/quant_crypto" $files
    if (-not $NoRestart) {
        ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && pkill -f 'fengji_radar_order_loop.py' 2>/dev/null || true; bash scripts/watchdog_overseas.sh 2>&1 | tail -6"
    }
}

if (-not $OverseasOnly) {
    Write-Host "=== Domestic ===" -ForegroundColor Cyan
    Sync-List "domestic-quant" "C:/Users/Administrator/quant_futures" $files
    if (-not $NoRestart) {
        scp -o BatchMode=yes (Join-Path $root "scripts/restart_domestic_radar_loop.ps1") "domestic-quant:C:/Users/Administrator/quant_futures/scripts/"
        ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -File C:/Users/Administrator/quant_futures/scripts/restart_domestic_radar_loop.ps1"
    }
}

Write-Host "=== Done ===" -ForegroundColor Green
