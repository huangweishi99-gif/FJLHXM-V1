#!/usr/bin/env bash
# Rebuild FengJi OS state after N04 break-rule + C-class defense fallback (2026-06-10).
set -euo pipefail

ROOT="${ROOT:-/home/ubuntu/quant_crypto}"
PROFILE="${PROFILE:-overseas}"
cd "$ROOT"

export FENGJI_MARKET=crypto
export PYTHONPATH=src:packages/fengji_core

echo "[1/8] verify os_engine N04 ..."
.venv/bin/python scripts/verify_os_engine_n04.py

echo "[2/8] stop radar/pending/paper/data_manager ..."
pkill -f 'fengji_radar_order_loop.py|fengji_pending_order_monitor.py|overseas_paper_monitor.py|data_manager.py|fengji_total_radar.py' || true
sleep 2

stamp="$(date +%Y%m%d_%H%M%S)"
backup="runtime/fengji_os_state_backup_${stamp}"
rebuild="runtime/fengji_os_state_rebuild_${stamp}"
audit_dir="results/os_state_rebuild/${PROFILE}_${stamp}"

echo "[3/8] backup current state -> ${backup}"
cp -a runtime/fengji_os_state "$backup"

echo "[4/8] rebuild all D1/H1/15m states -> ${rebuild}"
.venv/bin/python scripts/rebuild_os_state_all.py \
  --input data/1d,market=crypto \
  --input data/1h,market=crypto \
  --input data/15m,market=crypto \
  --state-dir "$rebuild" \
  --audit-dir "$audit_dir" \
  --mode rebuild

echo "[5/8] diff before/after state ..."
.venv/bin/python scripts/audit_os_state_rebuild_impact.py \
  --before-dir "$backup" \
  --after-dir "$rebuild" \
  --out-dir "$audit_dir" \
  --label "$PROFILE"

echo "[6/8] fill supervision re-audit (720h) ..."
.venv/bin/python scripts/audit_paper_fills.py \
  --profile overseas \
  --since-hours 720 \
  --out-dir "${audit_dir}/fill_supervision" \
  --quiet || true

echo "[7/8] swap rebuilt state ..."
rm -rf runtime/fengji_os_state
cp -a "$rebuild" runtime/fengji_os_state
echo "SWAPPED_TO=${rebuild} BACKUP=${backup} AUDIT=${audit_dir}"

echo "[8/8] restart runtime ..."
bash scripts/restart_overseas_runtime.sh

echo "OS state N04 rebuild complete (${PROFILE})."
