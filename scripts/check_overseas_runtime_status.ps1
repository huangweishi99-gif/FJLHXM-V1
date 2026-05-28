# 国外服务器运行态检查（免密 SSH：overseas-quant）
param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteDir = '/home/ubuntu/quant_crypto'
)

$ErrorActionPreference = "Stop"
$remote = "cd `"$RemoteDir`" 2>/dev/null || cd ~/quant_crypto; " +
    "echo '===== HOST ====='; hostname; date '+%Y-%m-%d %H:%M:%S %z'; " +
    "echo ''; echo '===== PROCESSES ====='; " +
    "ps aux | grep -E 'data_manager|fengji|paper|radar|pending|quant' | grep -v grep || echo NO_MATCHING_PROCESS; " +
    "echo ''; echo '===== RADAR / PENDING MTIME ====='; " +
    "ls -la runtime/fengji_radar/radar.json 2>/dev/null || echo no_radar_json; " +
    "ls -la runtime/fengji_pending_orders/pending_orders.json 2>/dev/null || echo no_pending_json; " +
    "ls -la runtime/fengji_os_state 2>/dev/null | head -8 || echo no_os_state_dir; " +
    "echo ''; echo '===== OS STATE MODULE ====='; " +
    "test -f packages/fengji_core/fengji_core/os_state_store.py && echo os_state_store_ok || echo os_state_store_missing; " +
    "echo FENGJI_MARKET=\${FENGJI_MARKET:-crypto}; " +
    "echo ''; echo '===== DATA SAMPLE MTIME ====='; " +
    "ls -lt data/*_1D_*.csv 2>/dev/null | head -5 || ls -lt data/*.csv 2>/dev/null | head -5 || echo no_data_csv"

Write-Host "Connecting $SshHost ..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=20 $SshHost $remote
