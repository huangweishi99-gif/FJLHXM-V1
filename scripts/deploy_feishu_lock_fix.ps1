# 飞书告警修复：state 锁竞争 + DS03 fill 复核 + 海外 watchdog ack
param(
    [switch]$OverseasOnly,
    [switch]$DomesticOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$shared = @(
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "packages/fengji_core/fengji_core/state_lock.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py"
)
$overseasExtra = @(
    "src/fengji_pending_order_monitor.py",
    "scripts/watchdog_overseas.sh"
)
$domesticExtra = @(
    "src/fengji_pending_order_monitor.py",
    "src/fengji_futures_pending_order_monitor.py"
)

function Sync-List([string]$HostAlias, [string]$RemoteRoot, [string[]]$Files) {
    foreach ($rel in $Files) {
        $local = Join-Path $root ($rel -replace "/", "\")
        if (-not (Test-Path -LiteralPath $local)) { throw "missing: $local" }
        $remote = "$RemoteRoot/$($rel -replace '\\','/')"
        scp -o BatchMode=yes -o ConnectTimeout=20 $local "${HostAlias}:$remote"
        if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
        Write-Host "synced ${HostAlias}: $rel"
    }
}

if (-not $DomesticOnly) {
    Write-Host "=== Overseas ===" -ForegroundColor Cyan
    Sync-List "overseas-quant" "/home/ubuntu/quant_crypto" ($shared + $overseasExtra)
    ssh -o BatchMode=yes overseas-quant "cd /home/ubuntu/quant_crypto && pkill -f 'src/fengji_pending_order_monitor.py' 2>/dev/null || true; bash scripts/watchdog_overseas.sh 2>&1 | tail -5"
}

if (-not $OverseasOnly) {
    Write-Host "=== Domestic ===" -ForegroundColor Cyan
    Sync-List "domestic-quant" "C:/Users/Administrator/quant_futures" ($shared + $domesticExtra)
    scp -o BatchMode=yes scripts/restart_domestic_pending_monitor.ps1 domestic-quant:C:/Users/Administrator/quant_futures/scripts/
    ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Administrator/quant_futures/scripts/restart_domestic_pending_monitor.ps1"
}

Write-Host "=== Done ===" -ForegroundColor Green
