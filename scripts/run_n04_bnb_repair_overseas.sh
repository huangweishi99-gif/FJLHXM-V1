#!/usr/bin/env bash
# N04 BNB DS01 audit_invalid + optional equity rollback on overseas crypto paper.
set -euo pipefail

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

ROOT="${ROOT:-/home/ubuntu/quant_crypto}"
cd "$ROOT"
export PYTHONPATH=src:packages/fengji_core
PY=.venv/bin/python

ORDER_ID="BNBUSDT-DS01-D1-long-ebfd3882424f3fc6"
REASON="N04 OS rebuild BNBUSDT_1d red->blue; DS01 long wrong_direction audit_invalid 2026-06-10"
PAPER_STATE="runtime/fengji_paper/state.json"
MONITOR_STATE="runtime/fengji_pending_orders/state.json"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPAIR_OUT="runtime/n04_bnb_repair_overseas_${STAMP}.json"

echo "[1/4] BNB probe ..."
$PY - <<'PY'
import json
from pathlib import Path
oid = "BNBUSDT-DS01-D1-long-ebfd3882424f3fc6"
st = json.loads(Path("runtime/fengji_paper/state.json").read_text(encoding="utf-8"))
mon = json.loads(Path("runtime/fengji_pending_orders/state.json").read_text(encoding="utf-8"))
sym = (st.get("symbols") or {}).get("BNBUSDT") or {}
opens = [p for p in (sym.get("open_positions") or []) if isinstance(p, dict) and not p.get("closed")]
print("BNB_open_positions=", len(opens))
for p in opens:
    print(" ", p.get("strategy_id"), p.get("direction") or p.get("side"), p.get("entry_time"), p.get("order_id") or p.get("key"))
for key in ("filled_order_ids", "filled_setup_keys", "consumed_ds03_setup_keys"):
    hits = [v for v in (mon.get(key) or []) if oid in str(v)]
    print(key, "hits=", len(hits), hits[:3])
records = []
for coll in ("audit_invalid_closes", "closed_trades"):
    for rec in st.get(coll) or []:
        if str(rec.get("order_id") or "") == oid:
            records.append((coll, rec))
for rec in sym.get("closed_trades") or []:
    if str(rec.get("order_id") or "") == oid:
        records.append(("symbols.closed_trades", rec))
for rec in sym.get("audit_invalid_closes") or []:
    if str(rec.get("order_id") or "") == oid:
        records.append(("symbols.audit_invalid_closes", rec))
print("close_records=", len(records))
for label, rec in records[:5]:
    print(" ", label, "pnl=", rec.get("net_pnl"), "audit_invalid=", rec.get("audit_invalid"), "rollback=", rec.get("equity_rollback_applied"))
PY

echo "[2/4] repair_corrupt_futures_state_from_audit $(if [[ $APPLY -eq 1 ]]; then echo APPLY; else echo DRY-RUN; fi) ..."
REPAIR_ARGS=(
  scripts/repair_corrupt_futures_state_from_audit.py
  --audit runtime/m5_empty_audit.json
  --state "$PAPER_STATE"
  --monitor-state "$MONITOR_STATE"
  --order-id "$ORDER_ID"
  --reason "$REASON"
  --out "$REPAIR_OUT"
)
if [[ $APPLY -eq 1 ]]; then
  REPAIR_ARGS+=(--apply)
fi
$PY "${REPAIR_ARGS[@]}"

echo "[3/4] equity rollback dry-run (if close record exists) ..."
set +e
$PY scripts/apply_equity_rollback.py \
  --state "$PAPER_STATE" \
  --order-id "$ORDER_ID" \
  --reason "$REASON" \
  --dry-run > "runtime/n04_bnb_equity_rollback_${STAMP}.json" 2> "runtime/n04_bnb_equity_rollback_${STAMP}.err"
RB_EXIT=$?
set -e
if [[ $RB_EXIT -eq 0 ]]; then
  cat "runtime/n04_bnb_equity_rollback_${STAMP}.json"
  if [[ $APPLY -eq 1 ]]; then
    echo "[3b] equity rollback APPLY ..."
    $PY scripts/apply_equity_rollback.py \
      --state "$PAPER_STATE" \
      --order-id "$ORDER_ID" \
      --reason "$REASON"
  fi
else
  echo "equity_rollback_skip: no close record or already applied (see runtime/n04_bnb_equity_rollback_${STAMP}.err)"
fi

echo "[4/4] post-check ..."
$PY - <<'PY'
import json
from pathlib import Path
oid = "BNBUSDT-DS01-D1-long-ebfd3882424f3fc6"
st = json.loads(Path("runtime/fengji_paper/state.json").read_text(encoding="utf-8"))
mon = json.loads(Path("runtime/fengji_pending_orders/state.json").read_text(encoding="utf-8"))
sym = (st.get("symbols") or {}).get("BNBUSDT") or {}
opens = [p for p in (sym.get("open_positions") or []) if isinstance(p, dict) and not p.get("closed")]
print("BNB_open_positions_after=", len(opens))
hits = [v for v in (mon.get("filled_order_ids") or []) if oid in str(v)]
print("filled_order_ids hits_after=", len(hits))
PY

echo "repair_plan=$REPAIR_OUT apply=$APPLY"
