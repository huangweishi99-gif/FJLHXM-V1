# DS03 真峰防守极校验 + 海外 binance paper 飞书 dedup 桶
param(
    [switch]$OverseasOnly,
    [switch]$DomesticOnly,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$coreFiles = @("packages/fengji_core/fengji_core/ds03.py")
$overseasExtra = @("src/binance_fengji_paper_monitor.py")

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
    Sync-List "overseas-quant" "/home/ubuntu/quant_crypto" ($coreFiles + $overseasExtra)
    if (-not $NoRestart) {
        ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && pkill -f 'fengji_radar_order_loop.py' 2>/dev/null || true; bash scripts/watchdog_overseas.sh 2>&1 | tail -6"
    }
}

if (-not $OverseasOnly) {
    Write-Host "=== Domestic ===" -ForegroundColor Cyan
    Sync-List "domestic-quant" "C:/Users/Administrator/quant_futures" $coreFiles
    if (-not $NoRestart) {
        scp -o BatchMode=yes (Join-Path $root "scripts/restart_domestic_radar_loop.ps1") "domestic-quant:C:/Users/Administrator/quant_futures/scripts/"
        ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -File C:/Users/Administrator/quant_futures/scripts/restart_domestic_radar_loop.ps1"
    }
}

Write-Host "=== Done ===" -ForegroundColor Green
