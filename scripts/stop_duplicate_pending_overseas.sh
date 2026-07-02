#!/usr/bin/env bash
# 国外：只保留一个挂单监控进程，避免重复飞书平仓/开仓
set -euo pipefail
cd /home/ubuntu/quant_crypto
pids="$(pgrep -f 'src/fengji_pending_order_monitor.py' || true)"
if [ -z "$pids" ]; then
  echo "no fengji_pending_order_monitor process"
  exit 0
fi
count="$(echo "$pids" | wc -w | tr -d ' ')"
if [ "$count" -le 1 ]; then
  echo "ok: single pending monitor pid=$pids"
  exit 0
fi
echo "killing duplicate pending monitors: $pids"
kill $pids || true
sleep 2
echo "restart one pending monitor via restart_overseas_runtime.sh (pending section only)"
echo "run: bash scripts/restart_overseas_runtime.sh"
