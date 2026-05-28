$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
Set-Location $root
$env:PYTHONPATH = "src;packages/fengji_core"
$env:FENGJI_MARKET = "futures"
& $py -u src\fengji_radar_order_loop.py `
  --data-dir data `
  --radar-dir runtime\fengji_radar `
  --pending-dir runtime\fengji_pending_orders `
  --monitor-state runtime\fengji_pending_orders\futures_pending_state.json `
  --symbols "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC" `
  --include-triggered `
  --once `
  --daily-tail 400 `
  --h1-tail 2400 `
  --top-n 40
Write-Host "refresh_once_done"
