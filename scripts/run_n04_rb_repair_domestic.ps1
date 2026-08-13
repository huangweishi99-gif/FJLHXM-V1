# N04 RB DS01 audit_invalid: dry-run / apply repair on domestic futures paper + monitor locks.
param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Root = "C:/Users/Administrator/quant_futures"
Set-Location $Root
$env:PYTHONPATH = "$Root/src;$Root/packages/fengji_core"

$orderId = "RBUSDT-DS01-D1-short-5b4e7fd42ee68111"
$reason = "N04 OS rebuild RB_1d camp blue->red; DS01 short signal_camp mismatch audit_invalid 2026-06-10"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "runtime/n04_rb_repair_domestic_$stamp.json"

$paperState = "runtime/fengji_futures/state_futures_v2.json"
$monitorState = "runtime/fengji_pending_orders/futures_pending_state.json"

Write-Host "[1/3] RB open position / monitor lock probe ..." -ForegroundColor Cyan
python -c @"
import json
from pathlib import Path
oid = '$orderId'
state = json.loads(Path('$paperState').read_text(encoding='utf-8'))
mon = json.loads(Path('$monitorState').read_text(encoding='utf-8'))
rb = (state.get('symbols') or {}).get('RBUSDT') or (state.get('symbols') or {}).get('RB') or {}
opens = [p for p in (rb.get('open_positions') or []) if isinstance(p, dict) and not p.get('closed')]
print('RB_open_positions=', len(opens))
for p in opens:
    print(' ', p.get('strategy_id'), p.get('direction') or p.get('side'), p.get('entry_time'), p.get('order_id') or p.get('key'))
for key in ('filled_order_ids','filled_setup_keys','consumed_ds03_setup_keys'):
    vals = mon.get(key) or []
    hits = [v for v in vals if oid in str(v)]
    print(key, 'hits=', len(hits), hits[:3])
"@

Write-Host "[2/3] repair_corrupt_futures_state_from_audit $(if ($Apply) { 'APPLY' } else { 'DRY-RUN' }) ..." -ForegroundColor Cyan
$args = @(
    "scripts/repair_corrupt_futures_state_from_audit.py",
    "--audit", "runtime/m5_empty_audit.json",
    "--state", $paperState,
    "--monitor-state", $monitorState,
    "--order-id", $orderId,
    "--reason", $reason,
    "--out", $out
)
if ($Apply) { $args += "--apply" }
python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/3] post-check ..." -ForegroundColor Cyan
python -c @"
import json
from pathlib import Path
oid = '$orderId'
state = json.loads(Path('$paperState').read_text(encoding='utf-8'))
mon = json.loads(Path('$monitorState').read_text(encoding='utf-8'))
rb = (state.get('symbols') or {}).get('RBUSDT') or (state.get('symbols') or {}).get('RB') or {}
opens = [p for p in (rb.get('open_positions') or []) if isinstance(p, dict) and not p.get('closed')]
print('RB_open_positions_after=', len(opens))
for key in ('filled_order_ids','filled_setup_keys'):
    vals = mon.get(key) or []
    hits = [v for v in vals if oid in str(v)]
    print(key, 'hits_after=', len(hits))
"@
Write-Host "repair_plan=$out apply=$($Apply.IsPresent)" -ForegroundColor Green
