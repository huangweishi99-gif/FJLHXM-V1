# 国内一键：同步核心 OS/定式/雷达文件 + 可选安装 fengji_core
param(
    [switch]$RestartRadarLoop,
    [switch]$RestartFuturesRuntime
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Remote = "domestic-quant"
$RemoteRoot = "C:/Users/Administrator/quant_futures"
$Core = Join-Path $Root "packages\fengji_core\fengji_core"

$syncMap = @(
    @{ Local = "$Core\os_engine.py"; Remote = "$RemoteRoot/src/quant/os_engine.py" },
    @{ Local = "$Core\ds01.py"; Remote = "$RemoteRoot/src/quant/ds01.py" },
    @{ Local = "$Core\ds03.py"; Remote = "$RemoteRoot/src/quant/ds03.py" },
    @{ Local = "$Core\ds05.py"; Remote = "$RemoteRoot/src/quant/ds05.py" },
    @{ Local = "$Core\ds07.py"; Remote = "$RemoteRoot/src/quant/ds07.py" },
    @{ Local = "$Core\ds09.py"; Remote = "$RemoteRoot/src/quant/ds09.py" },
    @{ Local = "$Core\os_state_store.py"; Remote = "$RemoteRoot/src/quant/os_state_store.py" },
    @{ Local = "$Root\src\fengji_total_radar.py"; Remote = "$RemoteRoot/src/fengji_total_radar.py" },
    @{ Local = "$Root\src\fengji_radar_order_loop.py"; Remote = "$RemoteRoot/src/fengji_radar_order_loop.py" },
    @{ Local = "$Root\src\fengji_pending_orders.py"; Remote = "$RemoteRoot/src/fengji_pending_orders.py" },
    @{ Local = "$Root\src\fengji_pending_order_monitor.py"; Remote = "$RemoteRoot/src/fengji_pending_order_monitor.py" },
    @{ Local = "$Root\src\fengji_futures_pending_order_monitor.py"; Remote = "$RemoteRoot/src/fengji_futures_pending_order_monitor.py" },
    @{ Local = "$Root\src\fengji_feishu_notify.py"; Remote = "$RemoteRoot/src/fengji_feishu_notify.py" },
    @{ Local = "$Root\scripts\stop_duplicate_pending_domestic.ps1"; Remote = "$RemoteRoot/scripts/stop_duplicate_pending_domestic.ps1" },
    @{ Local = "$Root\data_manager_futures.py"; Remote = "$RemoteRoot/data_manager_futures.py" },
    @{ Local = "$Root\remote_domestic_optimize\峰极总定式01-08国内期货A股模拟实盘.py"; Remote = "$RemoteRoot/峰极总定式01-08国内期货A股模拟实盘.py" },
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
    @{ Local = "$Root\src\plot_ds09_sandbox.py"; Remote = "$RemoteRoot/src/plot_ds09_sandbox.py" }
)

Write-Host "[1/3] sync core files to domestic ..." -ForegroundColor Cyan
foreach ($item in $syncMap) {
    if (-not (Test-Path $item.Local)) { throw "Missing local file: $($item.Local)" }
    scp -o BatchMode=yes $item.Local "${Remote}:$($item.Remote)"
    Write-Host "  OK $($item.Remote)" -ForegroundColor DarkGray
}

Write-Host "[2/3] sync fengji_core package ..." -ForegroundColor Cyan
ssh -o BatchMode=yes $Remote "if (-not (Test-Path '$RemoteRoot/packages')) { New-Item -ItemType Directory -Path '$RemoteRoot/packages' | Out-Null }"
scp -o BatchMode=yes -r (Join-Path $Root "packages\fengji_core") "${Remote}:${RemoteRoot}/packages/fengji_core"
ssh -o BatchMode=yes $Remote "cd '$RemoteRoot'; if (Test-Path .venv/Scripts/pip.exe) { .venv/Scripts/pip.exe install -e packages/fengji_core -q } elseif (Test-Path 'C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe') { & 'C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe' -m pip install -e packages/fengji_core -q } else { py -3 -m pip install -e packages/fengji_core -q }"

if ($RestartFuturesRuntime) {
    Write-Host "[3/3] restart domestic futures runtime (data pump + radar + pending) ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes $Remote "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/restart_domestic_futures_runtime.ps1'"
} elseif ($RestartRadarLoop) {
    Write-Host "[3/3] restart radar loop ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes $Remote "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/restart_domestic_radar_loop.ps1'"
} else {
    Write-Host "[3/3] skip restart (use -RestartFuturesRuntime or -RestartRadarLoop)" -ForegroundColor DarkGray
}

Write-Host "`nDomestic core sync done." -ForegroundColor Green
