#!/usr/bin/env bash
# 海外运行时看护：进程掉了自动拉起 + 数据停更飞书告警（带冷却防刷屏）。
# 建议 cron 每分钟跑一次：
#   * * * * * /home/ubuntu/quant_crypto/scripts/watchdog_overseas.sh >> /home/ubuntu/quant_crypto/runtime/logs/watchdog.log 2>&1
set -uo pipefail

ROOT="/home/ubuntu/quant_crypto"
cd "$ROOT" || exit 1

PY="$ROOT/.venv/bin/python"
export FENGJI_MARKET="${FENGJI_MARKET:-crypto}"
STATE_DIR="$ROOT/runtime/watchdog"
mkdir -p "$STATE_DIR" "$ROOT/runtime/logs"

# 单实例：防止 cron 与人工/部署脚本并发看护互相踩踏
LOCK_FILE="$STATE_DIR/watchdog.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] watchdog skip (another instance running)"
  exit 0
fi

if [ -f "$ROOT/runtime/feishu_webhook.env" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/runtime/feishu_webhook.env"
fi
WEBHOOK="${FEISHU_WEBHOOK:-}"

# 告警冷却（秒）：同一告警 key 在窗口内只发一次
ALERT_COOLDOWN="${WATCHDOG_ALERT_COOLDOWN:-1800}"
# 数据停更阈值（秒）：海外 7x24，超过即异常
DATA_STALE_LIMIT="${WATCHDOG_DATA_STALE_LIMIT:-1800}"
# 雷达停更阈值（秒）：loop=900s，给 2.5 倍裕量
RADAR_STALE_LIMIT="${WATCHDOG_RADAR_STALE_LIMIT:-2400}"
FILL_SUPERVISION_INTERVAL="${WATCHDOG_FILL_SUPERVISION_INTERVAL:-1800}"
# OKX 15m（HYPE/ATH 等 Binance 无源品种），默认 10 分钟，对齐 data_manager 周期
OKX_15M_INTERVAL="${WATCHDOG_OKX_15M_INTERVAL:-600}"

okx_15m_due() {
  local stamp="$STATE_DIR/okx_15m.last"
  if [ ! -f "$stamp" ]; then return 0; fi
  local now mtime
  now="$(date +%s)"
  mtime="$(stat -c %Y "$stamp" 2>/dev/null || echo 0)"
  [ $((now - mtime)) -ge "$OKX_15M_INTERVAL" ]
}

run_okx_15m_sync() {
  local sync="$ROOT/scripts/sync_missing_crypto_15m.py"
  if [ ! -f "$sync" ]; then return 0; fi
  echo "[$(ts)] okx_15m_sync start"
  export PYTHONPATH="$ROOT/src:$ROOT/packages/fengji_core:$ROOT/services:$ROOT/scripts"
  if "$PY" "$sync" --symbols HYPEUSDT,ATHUSDT --timeframes M15,D1,H1 --force-okx --fix-os --root "$ROOT" >> "$ROOT/runtime/logs/okx_15m_sync.log" 2>&1; then
    clear_alert "okx_15m_sync"
    echo "[$(ts)] okx_15m_sync ok (M15+D1+H1)"
    if ! "$PY" "$ROOT/scripts/check_okx_csv_freshness.py" --root "$ROOT" >> "$ROOT/runtime/logs/okx_15m_sync.log" 2>&1; then
      send_feishu "okx_csv_stale" "OKX HYPE/ATH CSV 末根滞后（时区/游标异常），见 runtime/logs/okx_15m_sync.log"
    else
      clear_alert "okx_csv_stale"
    fi
  else
    send_feishu "okx_15m_sync" "OKX K线同步失败（HYPE/ATH M15+D1+H1），见 runtime/logs/okx_15m_sync.log"
  fi
  date '+%Y-%m-%d %H:%M:%S' > "$STATE_DIR/okx_15m.last"
}

fill_supervision_due() {
  local stamp="$STATE_DIR/fill_supervision.last"
  if [ ! -f "$stamp" ]; then return 0; fi
  local now mtime
  now="$(date +%s)"
  mtime="$(stat -c %Y "$stamp" 2>/dev/null || echo 0)"
  [ $((now - mtime)) -ge "$FILL_SUPERVISION_INTERVAL" ]
}

run_fill_supervision() {
  local audit="$ROOT/scripts/audit_paper_fills.py"
  local events="$ROOT/runtime/fengji_pending_orders/events.jsonl"
  local ack="$ROOT/runtime/fill_supervision_acknowledged.json"
  if [ ! -f "$audit" ] || [ ! -f "$events" ]; then return 0; fi
  echo "[$(ts)] fill_supervision start"
  local ack_arg=""
  if [ -f "$ack" ]; then ack_arg="--ack-file $ack"; fi
  if "$PY" "$audit" --root "$ROOT" --profile overseas --since-hours 72 --fail-on-invalid $ack_arg --quiet; then
    clear_alert "fill_supervision_invalid"
    echo "[$(ts)] fill_supervision ok"
  else
    local code=$?
    date '+%Y-%m-%d %H:%M:%S' > "$STATE_DIR/fill_supervision.last"
    if [ "$code" -eq 2 ]; then
      send_feishu "fill_supervision_invalid" "成交后定式复核发现 INVALID 模拟成交（近72h），见 runtime/logs/fill_supervision/"
    else
      echo "[$(ts)] fill_supervision exit=$code"
    fi
  fi
  date '+%Y-%m-%d %H:%M:%S' > "$STATE_DIR/fill_supervision.last"
}

ts() { date '+%Y-%m-%d %H:%M:%S'; }

send_feishu() {
  # $1=alert_key  $2=message  —— 带冷却
  local key="$1" msg="$2"
  local stamp_file="$STATE_DIR/${key}.alert"
  local now last=0
  now="$(date +%s)"
  if [ -f "$stamp_file" ]; then last="$(cat "$stamp_file" 2>/dev/null || echo 0)"; fi
  if [ $((now - last)) -lt "$ALERT_COOLDOWN" ]; then
    return 0
  fi
  echo "$now" > "$stamp_file"
  echo "[$(ts)] ALERT[$key] $msg"
  if [ -n "$WEBHOOK" ]; then
    local payload
    payload="$(printf '{"msg_type":"text","content":{"text":"%s"}}' "🛡️【海外看护告警】\n时间: $(ts)\n$msg")"
    curl -s -m 8 -X POST -H 'Content-Type: application/json' -d "$payload" "$WEBHOOK" >/dev/null 2>&1 || true
  fi
}

clear_alert() { rm -f "$STATE_DIR/$1.alert" 2>/dev/null || true; }

newest_mtime_in() {
  # echo 最新文件的 mtime(秒)；无文件输出 0
  local dir="$1"
  local newest
  newest="$(ls -t "$dir"/*.csv 2>/dev/null | head -1)"
  if [ -z "$newest" ]; then echo 0; return; fi
  stat -c %Y "$newest" 2>/dev/null || echo 0
}

proc_alive() {
  pgrep -f "$1" >/dev/null 2>&1
}

ensure_proc() {
  # $1=进程匹配正则  $2=人类名  $3=拉起命令(字符串)
  # 拉起后多次探测 + 最多重试 3 次，避免部署 pkill 与 cron 竞态误报。
  local pat="$1" name="$2" cmd="$3"
  local attempt wait_s
  if proc_alive "$pat"; then
    clear_alert "proc_${name}"
    return 0
  fi
  echo "[$(ts)] $name 不在，拉起中..."
  for attempt in 1 2 3; do
    if proc_alive "$pat"; then
      clear_alert "proc_${name}"
      echo "[$(ts)] $name 已在运行 ✅"
      return 0
    fi
    bash -c "$cmd" < /dev/null
    for wait_s in 2 3 5; do
      sleep "$wait_s"
      if proc_alive "$pat"; then
        clear_alert "proc_${name}"
        echo "[$(ts)] $name 已自动拉起 ✅ (attempt=$attempt)"
        return 0
      fi
    done
    echo "[$(ts)] $name 拉起后未存活，重试 ($attempt/3)..."
  done
  send_feishu "proc_${name}" "进程【$name】掉线且自动拉起失败 ❌，请人工介入"
}

CMD_DATA="cd $ROOT && exec 9>&- && setsid $PY -u data_manager.py >> data_sync.log 2>&1 &"
CMD_RADAR="cd $ROOT && exec 9>&- && setsid env FENGJI_MARKET=$FENGJI_MARKET $PY -u src/fengji_radar_order_loop.py --market $FENGJI_MARKET --data-dir data --radar-dir runtime/fengji_radar --pending-dir runtime/fengji_pending_orders --monitor-state runtime/fengji_pending_orders/state.json --include-triggered --loop-seconds 900 --top-n 40 --daily-tail 1095 --h1-tail 2400 --m15-tail 960 >> radar_order_loop.log 2>&1 &"
CMD_PENDING="cd $ROOT && set -a && [ -f runtime/feishu_webhook.env ] && . runtime/feishu_webhook.env; set +a; exec 9>&- && setsid $PY -u src/fengji_pending_order_monitor.py --orders-file runtime/fengji_pending_orders/pending_orders.json --out-dir runtime/fengji_pending_orders --state-file runtime/fengji_pending_orders/state.json --paper-state-file runtime/fengji_paper/state.json --data-dir data --os-state-dir runtime/fengji_os_state --initial-cash 1000 --margin-per-trade 200 --leverage 2 --loop-seconds 5 >> pending_order_monitor.log 2>&1 &"
CMD_PAPER="cd $ROOT && set -a && [ -f runtime/feishu_webhook.env ] && . runtime/feishu_webhook.env; set +a; exec 9>&- && setsid $PY -u src/overseas_paper_monitor.py --data-dir data --initial-cash 1000 --margin-per-trade 200 --leverage 2 >> paper_run.log 2>&1 &"

ensure_proc "data_manager\.py"              "data_manager"   "$CMD_DATA"
ensure_proc "src/fengji_radar_order_loop\.py" "radar_loop"   "$CMD_RADAR"
ensure_proc "src/fengji_pending_order_monitor\.py" "pending_monitor" "$CMD_PENDING"
ensure_proc "src/overseas_paper_monitor\.py" "paper_monitor" "$CMD_PAPER"

NOW="$(date +%s)"

# 数据停更检查（海外 7x24）
DATA_MTIME="$(newest_mtime_in "$ROOT/data/15m")"
if [ "$DATA_MTIME" -gt 0 ]; then
  AGE=$((NOW - DATA_MTIME))
  if [ "$AGE" -gt "$DATA_STALE_LIMIT" ]; then
    send_feishu "data_stale" "15m 行情数据已 $((AGE/60)) 分钟未更新（阈值 $((DATA_STALE_LIMIT/60)) 分钟），疑似数据泵异常"
  else
    clear_alert "data_stale"
  fi
fi

# 雷达停更检查
RADAR_FILE="$ROOT/runtime/fengji_radar/radar.json"
if [ -f "$RADAR_FILE" ]; then
  RADAR_MTIME="$(stat -c %Y "$RADAR_FILE" 2>/dev/null || echo 0)"
  AGE=$((NOW - RADAR_MTIME))
  if [ "$AGE" -gt "$RADAR_STALE_LIMIT" ]; then
    send_feishu "radar_stale" "radar.json 已 $((AGE/60)) 分钟未刷新（阈值 $((RADAR_STALE_LIMIT/60)) 分钟），疑似雷达卡死"
  else
    clear_alert "radar_stale"
  fi
fi

if fill_supervision_due; then
  run_fill_supervision
fi

if okx_15m_due; then
  run_okx_15m_sync
fi

echo "[$(ts)] watchdog ok"
