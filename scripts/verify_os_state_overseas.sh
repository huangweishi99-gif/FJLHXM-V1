#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/quant_crypto
PY=.venv/bin/python
STATE=runtime/fengji_os_state/BTCUSDT_1d.json

stat_state() {
  $PY -c "
import json
from pathlib import Path
p=Path('$STATE')
st=json.loads(p.read_text()) if p.exists() else {}
print('size', p.stat().st_size if p.exists() else 0, 'processed_len', st.get('processed_len'), 'last_date', st.get('last_date'))
"
}

echo "=== BEFORE ==="
stat_state
SZ0=$(stat -c%s "$STATE" 2>/dev/null || echo 0)

echo "=== radar once #1 ==="
FENGJI_MARKET=crypto $PY -u src/fengji_radar_order_loop.py --once \
  --data-dir data --radar-dir runtime/fengji_radar \
  --pending-dir runtime/fengji_pending_orders \
  --monitor-state runtime/fengji_pending_orders/state.json \
  --symbols BTCUSDT --top-n 1 --daily-tail 400 --h1-tail 1200 | tail -3

echo "=== AFTER #1 ==="
stat_state
SZ1=$(stat -c%s "$STATE")
D1=$((SZ1 - SZ0))

echo "=== radar once #2 (same data) ==="
FENGJI_MARKET=crypto $PY -u src/fengji_radar_order_loop.py --once \
  --data-dir data --radar-dir runtime/fengji_radar \
  --pending-dir runtime/fengji_pending_orders \
  --monitor-state runtime/fengji_pending_orders/state.json \
  --symbols BTCUSDT --top-n 1 --daily-tail 400 --h1-tail 1200 | tail -3

echo "=== AFTER #2 ==="
stat_state
SZ2=$(stat -c%s "$STATE")
D2=$((SZ2 - SZ1))

echo "=== SUMMARY delta1=$D1 delta2=$D2 (delta2 should be << delta1 if incremental rewrite stable) ==="
if [ "$D2" -lt 100000 ] 2>/dev/null || [ "$D2" -eq 0 ] 2>/dev/null; then
  echo "INCREMENTAL_OK"
else
  echo "INCREMENTAL_WARN large_second_delta=$D2"
fi
