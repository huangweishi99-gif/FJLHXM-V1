# 在国外/国内服务器上验证 OS 状态库：记录雷达 --once 前后 BTC/LC 状态文件体积与 processed_len
param(
    [ValidateSet("overseas", "domestic")]
    [string]$Target = "overseas",
    [string]$Symbol = "",
    [int]$Tail = 400
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if ($Target -eq "overseas") {
    $SshHost = "overseas-quant"
    $RemoteDir = '/home/ubuntu/quant_crypto'
    $Py = ".venv/bin/python"
    $Market = "crypto"
    if (-not $Symbol) { $Symbol = "BTCUSDT" }
    $RadarLoop = "src/fengji_radar_order_loop.py"
    $MonitorState = "runtime/fengji_pending_orders/state.json"
} else {
    $SshHost = "domestic-quant"
    $RemoteDir = "C:/Users/Administrator/quant_futures"
    $Py = "C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe"
    $Market = "futures"
    if (-not $Symbol) { $Symbol = "LCUSDT" }
    $RadarLoop = "src/fengji_radar_order_loop.py"
    $MonitorState = "runtime/fengji_pending_orders/futures_pending_state.json"
}

$verifyLocal = Join-Path $Root "scripts\verify_os_state_incremental.py"
$remoteVerify = "$RemoteDir/scripts/verify_os_state_incremental.py"
scp -o BatchMode=yes $verifyLocal "${SshHost}:${remoteVerify}"

$statPy = @"
import json
from pathlib import Path
sym = '$Symbol'
p = Path('$RemoteDir/runtime/fengji_os_state') / (sym.replace('USDT','') + '_1d.json' if '$Market' == 'futures' else sym + '_1d.json')
if '$Market' == 'futures':
    p = Path('$RemoteDir/runtime/fengji_os_state/LC_1d.json')
else:
    p = Path('$RemoteDir/runtime/fengji_os_state/BTCUSDT_1d.json')
if not p.exists():
    p = Path('$RemoteDir/runtime/fengji_os_state') / (sym + '_1d.json')
st = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
print(json.dumps({'path': str(p), 'size': p.stat().st_size if p.exists() else 0, 'processed_len': st.get('processed_len'), 'last_date': st.get('last_date')}))
"@

function Invoke-RemotePy([string]$Code) {
    if ($Target -eq "overseas") {
        ssh -o BatchMode=yes $SshHost "cd $RemoteDir && $Py -c '$Code'"
    } else {
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Code))
        ssh -o BatchMode=yes $SshHost "powershell -NoProfile -EncodedCommand $encoded"
    }
}

Write-Host "=== $Target OS state BEFORE ===" -ForegroundColor Cyan
Invoke-RemotePy $statPy

$radarCmd = if ($Target -eq "overseas") {
    "cd $RemoteDir && FENGJI_MARKET=$Market $Py -u $RadarLoop --once --data-dir data --radar-dir runtime/fengji_radar --pending-dir runtime/fengji_pending_orders --monitor-state $MonitorState --symbols $Symbol --top-n 3 --daily-tail $Tail --h1-tail 1200 2>&1 | tail -5"
} else {
    "`$env:FENGJI_MARKET='$Market'; `$env:PYTHONPATH='src;packages/fengji_core'; Set-Location '$RemoteDir'; & '$Py' -u $RadarLoop --once --data-dir data --radar-dir runtime/fengji_radar --pending-dir runtime/fengji_pending_orders --monitor-state $MonitorState --symbols LC --top-n 3 --daily-tail $Tail --h1-tail 1200"
}

Write-Host "`n=== radar --once ===" -ForegroundColor Cyan
if ($Target -eq "overseas") {
    ssh -o BatchMode=yes $SshHost $radarCmd
} else {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($radarCmd))
    ssh -o BatchMode=yes $SshHost "powershell -NoProfile -EncodedCommand $encoded"
}

Write-Host "`n=== $Target OS state AFTER (1st radar) ===" -ForegroundColor Cyan
Invoke-RemotePy $statPy

Write-Host "`n=== second radar --once ===" -ForegroundColor Cyan
if ($Target -eq "overseas") {
    ssh -o BatchMode=yes $SshHost $radarCmd
} else {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($radarCmd))
    ssh -o BatchMode=yes $SshHost "powershell -NoProfile -EncodedCommand $encoded"
}

Write-Host "`n=== $Target OS state AFTER (2nd radar) ===" -ForegroundColor Cyan
Invoke-RemotePy $statPy

Write-Host "`nDone. Compare size deltas between runs (2nd should be much smaller than 1st if incremental)." -ForegroundColor Green
