#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/quant_crypto
export PYTHONPATH="src:packages/fengji_core"

echo "=== IOUSDT D1 tail ==="
tail -3 data/1d/IOUSDT.csv

echo ""
echo "=== one-shot radar refresh (IOUSDT only) ==="
.venv/bin/python -u src/fengji_radar_order_loop.py \
  --market crypto \
  --data-dir data \
  --radar-dir runtime/fengji_radar \
  --pending-dir runtime/fengji_pending_orders \
  --monitor-state runtime/fengji_pending_orders/state.json \
  --symbols IOUSDT \
  --include-triggered \
  --once \
  --top-n 10 \
  --daily-tail 400 \
  --h1-tail 2400

echo ""
echo "=== radar IOUSDT ==="
.venv/bin/python - <<'PY'
import json
from pathlib import Path

radar = json.loads(Path("runtime/fengji_radar/radar.json").read_text(encoding="utf-8"))
rows = [r for r in radar if r.get("symbol") == "IOUSDT"]
print("count", len(rows))
for r in rows:
    print(r.get("strategy_id"), r.get("side"), r.get("status"), r.get("trigger_price"), (r.get("reason") or "")[:100])

pending = json.loads(Path("runtime/fengji_pending_orders/pending_orders.json").read_text(encoding="utf-8"))
pio = [r for r in pending if isinstance(r, dict) and r.get("symbol") == "IOUSDT"]
print("pending", len(pio))
for r in pio:
    print(r.get("strategy_id"), r.get("status"), r.get("trigger_price"), r.get("radar_status"))
PY
