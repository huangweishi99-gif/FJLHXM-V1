# 国内一键：同步核心 OS/定式/雷达文件 + 可选安装 fengji_core
param(
    [switch]$RestartRadarLoop,
    [switch]$RestartFuturesRuntime,
    [switch]$SkipPaperDeploy
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Remote = "domestic-quant"
$RemoteRoot = "C:/Users/Administrator/quant_futures"
$PackageRoot = Join-Path $Root "packages\fengji_core"
$Core = Join-Path $PackageRoot "fengji_core"

function Sync-RemoteFile {
    param(
        [string]$Local,
        [string]$RemotePath
    )
    if (-not (Test-Path -LiteralPath $Local)) { throw "Missing local file: $Local" }
    $remoteDir = ($RemotePath -replace "\\", "/") -replace "/[^/]+$", ""
    if ($remoteDir) {
        ssh -o BatchMode=yes -o ConnectTimeout=20 $Remote "if (-not (Test-Path '$remoteDir')) { New-Item -ItemType Directory -Force -Path '$remoteDir' | Out-Null }"
    }
    scp -o BatchMode=yes -o ConnectTimeout=20 "$Local" "${Remote}:$RemotePath"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $Local" }
    Write-Host "  OK $RemotePath" -ForegroundColor DarkGray
}

$syncMap = @(
    @{ Local = "$Core\os_engine.py"; Remote = "$RemoteRoot/src/quant/os_engine.py" },
    @{ Local = "$Core\ds01.py"; Remote = "$RemoteRoot/src/quant/ds01.py" },
    @{ Local = "$Core\ds03.py"; Remote = "$RemoteRoot/src/quant/ds03.py" },
    @{ Local = "$Core\ds05.py"; Remote = "$RemoteRoot/src/quant/ds05.py" },
    @{ Local = "$Core\ds07.py"; Remote = "$RemoteRoot/src/quant/ds07.py" },
    @{ Local = "$Core\ds09.py"; Remote = "$RemoteRoot/src/quant/ds09.py" },
    @{ Local = "$Core\os_state_store.py"; Remote = "$RemoteRoot/src/quant/os_state_store.py" },
    @{ Local = "$Core\state_lock.py"; Remote = "$RemoteRoot/packages/fengji_core/fengji_core/state_lock.py" },
    @{ Local = "$Root\src\fengji_total_radar.py"; Remote = "$RemoteRoot/src/fengji_total_radar.py" },
    @{ Local = "$Root\src\fengji_radar_order_loop.py"; Remote = "$RemoteRoot/src/fengji_radar_order_loop.py" },
    @{ Local = "$Root\src\fengji_pending_orders.py"; Remote = "$RemoteRoot/src/fengji_pending_orders.py" },
    @{ Local = "$Root\src\fengji_pending_order_monitor.py"; Remote = "$RemoteRoot/src/fengji_pending_order_monitor.py" },
    @{ Local = "$Root\src\fengji_futures_pending_order_monitor.py"; Remote = "$RemoteRoot/src/fengji_futures_pending_order_monitor.py" },
    @{ Local = "$Root\src\fengji_feishu_notify.py"; Remote = "$RemoteRoot/src/fengji_feishu_notify.py" },
    @{ Local = "$Root\scripts\stop_duplicate_pending_domestic.ps1"; Remote = "$RemoteRoot/scripts/stop_duplicate_pending_domestic.ps1" },
    @{ Local = "$Root\data_manager_futures.py"; Remote = "$RemoteRoot/data_manager_futures.py" },
    @{ Local = "$Root\scripts\resolve_domestic_paper.ps1"; Remote = "$RemoteRoot/scripts/resolve_domestic_paper.ps1" },
    @{ Local = "$Root\scripts\domestic_paper_manifest.txt"; Remote = "$RemoteRoot/scripts/domestic_paper_manifest.txt" },
    @{ Local = "$Root\scripts\domestic_install_matplotlib.ps1"; Remote = "$RemoteRoot/scripts/domestic_install_matplotlib.ps1" },
    @{ Local = "$Root\scripts\stop_domestic_futures_runtime.ps1"; Remote = "$RemoteRoot/scripts/stop_domestic_futures_runtime.ps1" },
    @{ Local = "$Root\scripts\restart_domestic_data_manager.ps1"; Remote = "$RemoteRoot/scripts/restart_domestic_data_manager.ps1" },
    @{ Local = "$Root\scripts\run_futures_pending_monitor.ps1"; Remote = "$RemoteRoot/scripts/run_futures_pending_monitor.ps1" },
    @{ Local = "$Root\scripts\restart_domestic_pending_only.ps1"; Remote = "$RemoteRoot/scripts/restart_domestic_pending_only.ps1" },
    @{ Local = "$Root\scripts\restart_domestic_futures_runtime.ps1"; Remote = "$RemoteRoot/scripts/restart_domestic_futures_runtime.ps1" },
    @{ Local = "$Root\scripts\restart_domestic_radar_loop.ps1"; Remote = "$RemoteRoot/scripts/restart_domestic_radar_loop.ps1" },
    @{ Local = "$Root\scripts\check_domestic_status.ps1"; Remote = "$RemoteRoot/scripts/check_domestic_status.ps1" },
    @{ Local = "$Root\scripts\verify_ds09_lc_session.py"; Remote = "$RemoteRoot/scripts/verify_ds09_lc_session.py" },
    @{ Local = "$Root\scripts\plot_lc_ds09_session_overview.py"; Remote = "$RemoteRoot/scripts/plot_lc_ds09_session_overview.py" },
    @{ Local = "$Root\scripts\run_lc_ds09_domestic.ps1"; Remote = "$RemoteRoot/scripts/run_lc_ds09_domestic.ps1" },
    @{ Local = "$Root\src\plot_ds09_sandbox.py"; Remote = "$RemoteRoot/src/plot_ds09_sandbox.py" },
    @{ Local = "$Root\scripts\watchdog_domestic.ps1"; Remote = "$RemoteRoot/scripts/watchdog_domestic.ps1" },
    @{ Local = "$Root\scripts\ensure_single_data_manager.ps1"; Remote = "$RemoteRoot/scripts/ensure_single_data_manager.ps1" },
    @{ Local = "$Root\scripts\install_watchdog_domestic_task.ps1"; Remote = "$RemoteRoot/scripts/install_watchdog_domestic_task.ps1" },
    @{ Local = "$Root\scripts\verify_pg_sc_15m_csv.ps1"; Remote = "$RemoteRoot/scripts/verify_pg_sc_15m_csv.ps1" },
    @{ Local = "$Root\scripts\probe_domestic_futures_15m.py"; Remote = "$RemoteRoot/scripts/probe_domestic_futures_15m.py" },
    @{ Local = "$Root\scripts\run_night_session_pg_sc_checks.ps1"; Remote = "$RemoteRoot/scripts/run_night_session_pg_sc_checks.ps1" },
    @{ Local = "$Root\scripts\wait_pg_sc_15m_acceptance.ps1"; Remote = "$RemoteRoot/scripts/wait_pg_sc_15m_acceptance.ps1" },
    @{ Local = "$Root\docs\PG_SC_15M_ACCEPTANCE.md"; Remote = "$RemoteRoot/docs/PG_SC_15M_ACCEPTANCE.md" }
)

Write-Host "[1/4] sync core files to domestic ..." -ForegroundColor Cyan
foreach ($item in $syncMap) {
    Sync-RemoteFile -Local $item.Local -RemotePath $item.Remote
}

if (-not $SkipPaperDeploy) {
    Write-Host "[2/4] sync domestic paper script (manifest + ASCII temp path) ..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "deploy_domestic_paper_feishu.ps1")
} else {
    Write-Host "[2/4] skip paper deploy (-SkipPaperDeploy)" -ForegroundColor DarkGray
}

Write-Host "[3/4] sync fengji_core package files ..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=20 $Remote "if (-not (Test-Path '$RemoteRoot/packages/fengji_core/fengji_core')) { New-Item -ItemType Directory -Force -Path '$RemoteRoot/packages/fengji_core/fengji_core' | Out-Null }"
foreach ($pkgFile in Get-ChildItem -LiteralPath $Core -File -Filter "*.py") {
    Sync-RemoteFile -Local $pkgFile.FullName -RemotePath "$RemoteRoot/packages/fengji_core/fengji_core/$($pkgFile.Name)"
}
foreach ($name in @("pyproject.toml", "README.md")) {
    $local = Join-Path $PackageRoot $name
    if (Test-Path -LiteralPath $local) {
        Sync-RemoteFile -Local $local -RemotePath "$RemoteRoot/packages/fengji_core/$name"
    }
}
ssh -o BatchMode=yes -o ConnectTimeout=20 $Remote "cd '$RemoteRoot'; if (Test-Path .venv/Scripts/pip.exe) { .venv/Scripts/pip.exe install -e packages/fengji_core -q } elseif (Test-Path 'C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe') { & 'C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe' -m pip install -e packages/fengji_core -q } else { py -3 -m pip install -e packages/fengji_core -q }"

if ($RestartFuturesRuntime) {
    Write-Host "[4/4] restart domestic futures runtime (data pump + radar + pending) ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes -o ConnectTimeout=20 $Remote "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/restart_domestic_futures_runtime.ps1'"
} elseif ($RestartRadarLoop) {
    Write-Host "[4/4] restart radar loop ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes -o ConnectTimeout=20 $Remote "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/restart_domestic_radar_loop.ps1'"
} else {
    Write-Host "[4/4] skip restart (use -RestartFuturesRuntime or -RestartRadarLoop)" -ForegroundColor DarkGray
}

Write-Host "[post] ensure data_manager loaded synced code ..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=20 $Remote "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/ensure_single_data_manager.ps1'"

Write-Host "`nDomestic core sync done." -ForegroundColor Green
