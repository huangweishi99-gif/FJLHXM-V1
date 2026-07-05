# 国内：补数据状态 + 一轮雷达/挂单（不重启常驻进程）
$ErrorActionPreference = "Stop"
$Root = "C:\Users\guangwan\Documents\New project"
$Remote = "domestic-quant"
$RemoteRoot = "C:/Users/Administrator/quant_futures"

Write-Host "Trigger domestic radar once (remote)..." -ForegroundColor Cyan
ssh -o BatchMode=yes $Remote @"
powershell -NoProfile -Command "
  Set-Location '$RemoteRoot'
  `$env:PYTHONPATH='src;packages/fengji_core'
  `$env:FENGJI_MARKET='futures'
  & 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe' -u src\fengji_radar_order_loop.py `
    --market futures `
    --data-dir data --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders `
    --monitor-state runtime\fengji_pending_orders\futures_pending_state.json `
    --symbols 'LC,SA,RB' --include-triggered --once --daily-tail 400 --h1-tail 2400 --top-n 40
"
"@
