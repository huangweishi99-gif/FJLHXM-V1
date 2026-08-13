# DS03 攻击棍入场执行层 · 双端同步 + 重启挂单监控（不改定式/OS）
param(
    [switch]$OverseasOnly,
    [switch]$DomesticOnly,
    [string]$OverseasHost = "overseas-quant",
    [string]$DomesticHost = "domestic-quant",
    [string]$OverseasRoot = "/home/ubuntu/quant_crypto",
    [string]$DomesticRoot = "C:/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$overseasFiles = @(
    "src/fengji_pending_order_monitor.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py",
    "packages/fengji_core/fengji_core/fill_supervision.py"
)
$domesticFiles = @(
    "src/fengji_pending_order_monitor.py",
    "src/fengji_futures_pending_order_monitor.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py",
    "packages/fengji_core/fengji_core/fill_supervision.py"
)

function Sync-Files([string]$HostAlias, [string]$RemoteRoot, [string[]]$Files) {
    foreach ($rel in $Files) {
        $local = Join-Path $root ($rel -replace "/", "\")
        if (-not (Test-Path -LiteralPath $local)) { throw "missing local: $local" }
        $remote = "$RemoteRoot/$($rel -replace '\\','/')"
        scp -o BatchMode=yes -o ConnectTimeout=20 $local "${HostAlias}:$remote"
        if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel -> $HostAlias" }
        Write-Host "synced $HostAlias : $rel"
    }
}

if (-not $DomesticOnly) {
    Write-Host "=== Overseas sync (core hash bundle) ===" -ForegroundColor Cyan
    & (Join-Path $root "scripts\sync_overseas_core_hash_files.ps1")
    if ($LASTEXITCODE -ne 0) { throw "overseas hash compare failed" }
    Write-Host "=== Overseas restart pending monitor ===" -ForegroundColor Cyan
    ssh -o BatchMode=yes -o ConnectTimeout=30 $OverseasHost @"
cd $OverseasRoot && pkill -f 'src/fengji_pending_order_monitor.py' 2>/dev/null || true
bash scripts/watchdog_overseas.sh 2>&1 | tail -6
pgrep -af 'fengji_pending_order_monitor' || echo 'pending_monitor NOT RUNNING'
"@
}

if (-not $OverseasOnly) {
    Write-Host "=== Domestic sync ===" -ForegroundColor Cyan
    Sync-Files $DomesticHost $DomesticRoot $domesticFiles
    $restartLocal = Join-Path $root "scripts\restart_domestic_pending_monitor.ps1"
    scp -o BatchMode=yes -o ConnectTimeout=20 $restartLocal "${DomesticHost}:${DomesticRoot}/scripts/restart_domestic_pending_monitor.ps1"
    if ($LASTEXITCODE -ne 0) { throw "scp restart script failed" }
    Write-Host "=== Domestic restart pending monitor ===" -ForegroundColor Cyan
    ssh -o BatchMode=yes -o ConnectTimeout=30 $DomesticHost "powershell -NoProfile -ExecutionPolicy Bypass -File $DomesticRoot/scripts/restart_domestic_pending_monitor.ps1"
}

Write-Host "=== Done ===" -ForegroundColor Green
