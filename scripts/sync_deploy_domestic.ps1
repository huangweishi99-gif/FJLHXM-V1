# 国内一键：同步核心 OS/定式/雷达文件 + 可选安装 fengji_core
param(
    [switch]$RestartRadarLoop
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
    @{ Local = "$Root\src\fengji_total_radar.py"; Remote = "$RemoteRoot/src/fengji_total_radar.py" },
    @{ Local = "$Root\src\fengji_radar_order_loop.py"; Remote = "$RemoteRoot/src/fengji_radar_order_loop.py" },
    @{ Local = "$Root\src\fengji_pending_orders.py"; Remote = "$RemoteRoot/src/fengji_pending_orders.py" },
    @{ Local = "$Root\src\fengji_futures_pending_order_monitor.py"; Remote = "$RemoteRoot/src/fengji_futures_pending_order_monitor.py" },
    @{ Local = "$Root\data_manager_futures.py"; Remote = "$RemoteRoot/data_manager_futures.py" },
    @{ Local = "$Root\scripts\restart_domestic_futures_runtime.ps1"; Remote = "$RemoteRoot/scripts/restart_domestic_futures_runtime.ps1" },
    @{ Local = "$Root\scripts\restart_domestic_radar_loop.ps1"; Remote = "$RemoteRoot/scripts/restart_domestic_radar_loop.ps1" },
    @{ Local = "$Root\scripts\check_domestic_status.ps1"; Remote = "$RemoteRoot/scripts/check_domestic_status.ps1" }
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

if ($RestartRadarLoop) {
    Write-Host "[3/3] restart radar loop ..." -ForegroundColor Cyan
    ssh -o BatchMode=yes $Remote "powershell -NoProfile -ExecutionPolicy Bypass -File '$RemoteRoot/scripts/restart_domestic_radar_loop.ps1'"
} else {
    Write-Host "[3/3] skip radar restart (use -RestartRadarLoop to apply loop code)" -ForegroundColor DarkGray
}

Write-Host "`nDomestic core sync done." -ForegroundColor Green
