$ErrorActionPreference = "Stop"
$remote = @'
Set-Location C:\Users\Administrator\quant_futures
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$env:FENGJI_MARKET = "futures"
$env:PYTHONPATH = "src;packages/fengji_core"
$state = "runtime\fengji_os_state\LC_1d.json"
function Show-State {
  $st = Get-Content $state -Raw | ConvertFrom-Json
  $fi = Get-Item $state
  Write-Host "size $($fi.Length) processed_len $($st.processed_len) last_date $($st.last_date)"
}
Write-Host "=== BEFORE ==="
Show-State
$sz0 = (Get-Item $state).Length
Write-Host "=== radar once 1 ==="
& $py -u src\fengji_radar_order_loop.py --once --data-dir data --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state runtime\fengji_pending_orders\futures_pending_state.json --symbols LC --top-n 1 --daily-tail 400 --h1-tail 2400 2>&1 | Select-Object -Last 3
Write-Host "=== AFTER 1 ==="
Show-State
$sz1 = (Get-Item $state).Length
Write-Host "=== radar once 2 ==="
& $py -u src\fengji_radar_order_loop.py --once --data-dir data --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state runtime\fengji_pending_orders\futures_pending_state.json --symbols LC --top-n 1 --daily-tail 400 --h1-tail 2400 2>&1 | Select-Object -Last 3
Write-Host "=== AFTER 2 ==="
Show-State
$sz2 = (Get-Item $state).Length
Write-Host "delta1=$($sz1-$sz0) delta2=$($sz2-$sz1)"
'@
$enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remote))
ssh -o BatchMode=yes domestic-quant "powershell -NoProfile -EncodedCommand $enc"
