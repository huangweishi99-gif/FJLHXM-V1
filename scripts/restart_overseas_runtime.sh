#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/quant_crypto

export FENGJI_MARKET="${FENGJI_MARKET:-crypto}"
mkdir -p runtime/fengji_os_state runtime/fengji_radar runtime/fengji_pending_orders runtime/fengji_paper runtime/logs

if [ -f runtime/feishu_webhook.env ]; then
  # shellcheck disable=SC1091
  source runtime/feishu_webhook.env
fi

runtime_pids="$(pgrep -f 'fengji_radar_order_loop.py|fengji_pending_order_monitor.py|overseas_paper_monitor.py' || true)"
if [ -n "$runtime_pids" ]; then
  kill $runtime_pids || true
  sleep 2
fi

dm_pids="$(pgrep -f 'data_manager.py' || true)"
if [ -n "$dm_pids" ]; then
  kill $dm_pids || true
  sleep 1
fi

setsid .venv/bin/python -u data_manager.py > data_sync.log 2>&1 &

# 2核4G：拉长循环、收敛 tail/top-n，避免并行全量雷达吃满内存
setsid env FENGJI_MARKET="${FENGJI_MARKET}" .venv/bin/python -u src/fengji_radar_order_loop.py \
  --data-dir data \
  --radar-dir runtime/fengji_radar \
  --pending-dir runtime/fengji_pending_orders \
  --monitor-state runtime/fengji_pending_orders/state.json \
  --include-triggered \
  --loop-seconds 900 \
  --top-n 40 \
  --daily-tail 400 \
  --h1-tail 2400 \
  > radar_order_loop.log 2>&1 &

FEISHU_WEBHOOK="${FEISHU_WEBHOOK:-}" setsid .venv/bin/python -u src/fengji_pending_order_monitor.py \
  --orders-file runtime/fengji_pending_orders/pending_orders.json \
  --out-dir runtime/fengji_pending_orders \
  --state-file runtime/fengji_pending_orders/state.json \
  --paper-state-file runtime/fengji_paper/state.json \
  --initial-cash 1000 \
  --margin-per-trade 200 \
  --leverage 2 \
  --loop-seconds 5 \
  > pending_order_monitor.log 2>&1 &

FEISHU_WEBHOOK="${FEISHU_WEBHOOK:-}" setsid .venv/bin/python -u src/overseas_paper_monitor.py \
  --data-dir data \
  --initial-cash 1000 \
  --margin-per-trade 200 \
  --leverage 2 \
  > paper_run.log 2>&1 &

sleep 3
pgrep -af 'data_manager.py|overseas_paper_monitor|fengji_radar_order_loop|fengji_pending_order_monitor' || true
