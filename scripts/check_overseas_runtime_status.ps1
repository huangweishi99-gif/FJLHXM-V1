# 国外服务器运行态检查（免密 SSH：overseas-quant）
param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteDir = '/home/ubuntu/quant_crypto'
)

$ErrorActionPreference = "Stop"
$remoteDirSafe = $RemoteDir.Replace("'", "'\''")
$remote = @'
cd '__REMOTE_DIR__' 2>/dev/null || cd ~/quant_crypto
echo '===== HOST ====='
hostname
date '+%Y-%m-%d %H:%M:%S %z'
echo ''
echo '===== PROCESSES ====='
ps aux | grep -E 'data_manager|fengji|paper|radar|pending|quant' | grep -v grep || echo NO_MATCHING_PROCESS
echo ''
echo '===== RADAR / PENDING MTIME ====='
ls -la runtime/fengji_radar/radar.json 2>/dev/null || echo no_radar_json
ls -la runtime/fengji_pending_orders/pending_orders.json 2>/dev/null || echo no_pending_json
ls -la runtime/fengji_os_state 2>/dev/null | head -8 || echo no_os_state_dir
echo ''
echo '===== OS STATE MODULE ====='
test -f packages/fengji_core/fengji_core/os_state_store.py && echo os_state_store_ok || echo os_state_store_missing
echo "FENGJI_MARKET=${FENGJI_MARKET:-crypto}"
if test -x .venv/bin/python; then
  PYTHON_BIN=.venv/bin/python
else
  PYTHON_BIN=python3
fi
echo "PYTHON_BIN=${PYTHON_BIN}"
echo ''
echo '===== DATA SAMPLE MTIME ====='
find data -maxdepth 2 -type f -name '*.csv' -printf '%T@ %TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort -nr | head -5 || echo no_data_csv
echo ''
echo '===== EFFECTIVE PENDING STATUS ====='
if test -f scripts/summarize_pending_effective_status.py; then
  PYTHONPATH=src:packages/fengji_core:. "$PYTHON_BIN" scripts/summarize_pending_effective_status.py --orders-file runtime/fengji_pending_orders/pending_orders.json --state-file runtime/fengji_pending_orders/state.json --paper-state-file runtime/fengji_paper/state.json --include-shadow 2>/dev/null | head -25
else
  echo 'effective pending summary unavailable: scripts/summarize_pending_effective_status.py not deployed'
fi
echo ''
echo '===== OVERSEAS NOTIFICATION AUDIT ====='
if test -f scripts/audit_overseas_notification_coverage.py; then
  PYTHONPATH=src:packages/fengji_core:. "$PYTHON_BIN" scripts/audit_overseas_notification_coverage.py
else
  echo 'overseas notification audit unavailable: scripts/audit_overseas_notification_coverage.py not deployed'
fi
'@.Replace("__REMOTE_DIR__", $remoteDirSafe)

Write-Host "Connecting $SshHost ..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=20 $SshHost $remote
