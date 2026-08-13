#!/usr/bin/env bash
# Complete N04 OS state swap + fill audit + restart when rebuild already finished.
set -euo pipefail

ROOT="${ROOT:-/home/ubuntu/quant_crypto}"
REBUILD_DIR="${1:-}"
PROFILE="${PROFILE:-overseas}"
cd "$ROOT"

if [[ -z "$REBUILD_DIR" || ! -d "$REBUILD_DIR" ]]; then
  echo "usage: $0 <rebuild_dir>" >&2
  exit 1
fi

export FENGJI_MARKET=crypto
export PYTHONPATH=src:packages/fengji_core

stamp="$(basename "$REBUILD_DIR" | sed -n 's/.*_rebuild_//p')"
backup="runtime/fengji_os_state_backup_${stamp}"
audit_dir="results/os_state_rebuild/${PROFILE}_complete"

echo "[1/4] swap state ..."
rm -rf runtime/fengji_os_state
cp -a "$REBUILD_DIR" runtime/fengji_os_state
echo "SWAPPED from ${REBUILD_DIR}"

echo "[2/4] diff ..."
if [[ -d "$backup" ]]; then
  .venv/bin/python scripts/audit_os_state_rebuild_impact.py \
    --before-dir "$backup" \
    --after-dir "$REBUILD_DIR" \
    --out-dir "$audit_dir" \
    --label "$PROFILE"
fi

echo "[3/4] fill supervision re-audit ..."
.venv/bin/python scripts/audit_paper_fills.py \
  --profile overseas \
  --since-hours 720 \
  --out-dir "${audit_dir}/fill_supervision" \
  --quiet || true

echo "[4/4] restart runtime ..."
bash scripts/restart_overseas_runtime.sh
echo "Complete swap done (${PROFILE})."
