#!/usr/bin/env bash
# OKX 15m for Binance-missing symbols (HYPE/ATH) + OS state incremental fix
set -euo pipefail
ROOT="${ROOT:-/home/ubuntu/quant_crypto}"
cd "$ROOT"
export FENGJI_MARKET=crypto
export PYTHONPATH=src:packages/fengji_core:services:scripts

echo "[1/3] OKX 15m ingest HYPE/ATH ..."
.venv/bin/python scripts/sync_missing_crypto_15m.py --symbols HYPEUSDT,ATHUSDT --force-okx

echo "[2/3] OS state incremental fix (crypto) ..."
.venv/bin/python scripts/audit_os_state_freshness_all.py --market crypto --fix --quiet

echo "[3/3] verify 15m files ..."
ls -la data/15m/HYPEUSDT.csv data/15m/ATHUSDT.csv
tail -1 runtime/logs/os_freshness_run.log 2>/dev/null || true
echo "OKX_15M_SYNC_DONE"
