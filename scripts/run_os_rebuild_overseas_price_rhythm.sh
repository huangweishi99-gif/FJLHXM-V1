#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/quant_crypto

export FENGJI_MARKET=crypto
export PYTHONPATH=src:packages/fengji_core

.venv/bin/python -c "from fengji_core.os_engine import FengJiOSIdentityEngine; assert hasattr(FengJiOSIdentityEngine, '_can_connect_opposite_nodes'); print('OS_ENGINE_OK')"

# Stop radar/pending/paper/data_manager before rebuild.
pkill -f 'fengji_radar_order_loop.py|fengji_pending_order_monitor.py|overseas_paper_monitor.py|data_manager.py|fengji_total_radar.py' || true
sleep 2

stamp="$(date +%Y%m%d_%H%M%S)"
backup="runtime/fengji_os_state_backup_${stamp}"
rebuild="runtime/fengji_os_state_rebuild_${stamp}"
cp -a runtime/fengji_os_state "$backup"

.venv/bin/python scripts/rebuild_os_state_all.py \
  --input data/1d,market=crypto \
  --input data/1h,market=crypto \
  --input data/15m,market=crypto \
  --state-dir "$rebuild" \
  --mode rebuild

rm -rf runtime/fengji_os_state
cp -a "$rebuild" runtime/fengji_os_state
echo "SWAPPED_TO=${rebuild} BACKUP=${backup}"

bash scripts/restart_overseas_runtime.sh
