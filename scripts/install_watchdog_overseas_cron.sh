#!/usr/bin/env bash
# 一次性安装海外 watchdog cron（每分钟）
set -euo pipefail
ROOT="/home/ubuntu/quant_crypto"
LINE="* * * * * ${ROOT}/scripts/watchdog_overseas.sh >> ${ROOT}/runtime/logs/watchdog.log 2>&1"
mkdir -p "${ROOT}/runtime/logs"
( crontab -l 2>/dev/null | grep -v watchdog_overseas || true; echo "$LINE" ) | crontab -
echo "crontab installed:"
crontab -l | grep watchdog_overseas
