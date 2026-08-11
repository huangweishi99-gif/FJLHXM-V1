@echo off
cd /d C:\Users\Administrator\quant_futures
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

if not exist runtime\logs mkdir runtime\logs

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'data_manager_futures|01-08|Dash.py|run_data_manager_futures|run_futures_astock_paper|fengji_radar_order_loop|fengji_futures_pending_order_monitor|run_futures_radar_loop|run_futures_pending_monitor' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

start "fengji_data_manager" /min cmd /c "C:\Users\Administrator\quant_futures\run_data_manager_futures.cmd"

start "fengji_paper" /min powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Administrator\quant_futures\run_futures_astock_paper.ps1"

start "fengji_radar_loop" /min cmd /c "C:\Users\Administrator\quant_futures\scripts\run_futures_radar_loop.cmd"

start "fengji_pending_monitor" /min cmd /c "C:\Users\Administrator\quant_futures\scripts\run_futures_pending_monitor.cmd"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$root='C:\Users\Administrator\quant_futures'; $py='C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe'; $dash=(Get-ChildItem -LiteralPath $root -File | Where-Object { $_.Name -like '*Dash.py' } | Select-Object -First 1 -ExpandProperty FullName); if ($dash) { Start-Process -FilePath $py -ArgumentList @($dash) -WorkingDirectory $root -WindowStyle Minimized }"

timeout /t 5
exit
