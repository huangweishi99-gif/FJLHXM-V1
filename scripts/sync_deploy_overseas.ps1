# 国外一键：同步 src + fengji_core + 关键入口文件，可选重启运行时
param(
    [switch]$Restart,
    [switch]$SkipSrc
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Remote = "overseas-quant"
# 必须用单引号，避免 PowerShell 把 /home 里的 $home 当成用户目录变量
$RemoteDir = '/home/ubuntu/quant_crypto'
$PaperLocal = Join-Path $Root "src\overseas_paper_monitor.py"
$CoreLocal = Join-Path $Root "packages\fengji_core"
$DataMgr = Join-Path $Root "data_manager.py"
$RestartSh = Join-Path $Root "scripts\restart_overseas_runtime.sh"

function Invoke-Remote([string]$Cmd) {
    ssh -o BatchMode=yes $Remote $Cmd
}

function Sync-RemoteFile([string]$RelPath) {
    $local = Join-Path $Root ($RelPath -replace '/', '\')
    if (-not (Test-Path $local)) { throw "Missing: $local" }
    $remoteRel = ($RelPath -replace '\\', '/')
    $slash = $remoteRel.LastIndexOf('/')
    if ($slash -gt 0) {
        $parent = $remoteRel.Substring(0, $slash)
        Invoke-Remote "mkdir -p ${RemoteDir}/${parent}"
    }
    scp -o BatchMode=yes $local "${Remote}:${RemoteDir}/${remoteRel}"
    Write-Host "  OK $remoteRel" -ForegroundColor DarkGray
}

if (-not $SkipSrc) {
    Write-Host "[1/5] sync src ..." -ForegroundColor Cyan
    & (Join-Path $Root "sync_src_to_server.ps1")
    Invoke-Remote "cd $RemoteDir && unzip -q -o src.zip && find src -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null; echo SRC_UNZIP_OK"
} else {
    Write-Host "[1/5] skip src (-SkipSrc)" -ForegroundColor DarkGray
}

Write-Host "[2/5] sync fengji_core ..." -ForegroundColor Cyan
Invoke-Remote "mkdir -p ${RemoteDir}/packages"
scp -o BatchMode=yes -r $CoreLocal "${Remote}:${RemoteDir}/packages/fengji_core"
Invoke-Remote "cd $RemoteDir && .venv/bin/pip install -e packages/fengji_core -q"

Write-Host "[3/5] sync OS state + radar/pending ..." -ForegroundColor Cyan
@(
    "packages/fengji_core/fengji_core/os_state_store.py",
    "src/fengji_total_radar.py",
    "src/fengji_radar_order_loop.py",
    "src/fengji_pending_orders.py",
    "src/fengji_pending_order_monitor.py",
    "src/fengji_feishu_notify.py",
    "scripts/stop_duplicate_pending_overseas.sh",
    "scripts/watchdog_overseas.sh",
    "scripts/rotate_log_tail.py",
    "docs/OS_STATE_DATA_STOCK.md"
) | ForEach-Object { Sync-RemoteFile $_ }
Invoke-Remote "cd $RemoteDir && cp -f packages/fengji_core/fengji_core/os_state_store.py src/quant/os_state_store.py 2>/dev/null || true; mkdir -p runtime/fengji_os_state"
Sync-RemoteFile "data_manager.py"
scp -o BatchMode=yes $PaperLocal "${Remote}:${RemoteDir}/src/overseas_paper_monitor.py"
Sync-RemoteFile "scripts/restart_overseas_runtime.sh"
Invoke-Remote "chmod +x ${RemoteDir}/scripts/restart_overseas_runtime.sh ${RemoteDir}/scripts/watchdog_overseas.sh"

if ($Restart) {
    Write-Host "[4/5] restart runtime ..." -ForegroundColor Cyan
    Invoke-Remote "cd $RemoteDir && bash scripts/restart_overseas_runtime.sh"
} else {
    Write-Host "[4/5] start data_manager only (no full restart) ..." -ForegroundColor Cyan
    Invoke-Remote "cd $RemoteDir; if pgrep -f data_manager.py >/dev/null; then echo data_manager_already_running; else setsid .venv/bin/python -u data_manager.py >> data_sync.log 2>&1 & echo data_manager_started; fi"
}

Write-Host "[5/5] status ..." -ForegroundColor Cyan
& (Join-Path $Root "scripts\check_overseas_runtime_status.ps1")

Write-Host "`nOverseas deploy done." -ForegroundColor Green
