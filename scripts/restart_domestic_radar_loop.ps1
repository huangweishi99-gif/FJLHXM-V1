$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$symbols = "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC"

Set-Location $root
New-Item -ItemType Directory -Force -Path runtime\logs | Out-Null

Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*fengji_radar_order_loop.py*" } |
    ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
    }

Start-Sleep -Seconds 1

$stateFile = "runtime\fengji_pending_orders\futures_pending_state.json"
$cmd = "cmd.exe /d /c cd /d `"$root`" && set `"PYTHONPATH=src;packages/fengji_core`"&& set FENGJI_MARKET=futures&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& `"$py`" -u `"src\fengji_radar_order_loop.py`" --data-dir data --symbols `"$symbols`" --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state `"$stateFile`" --include-triggered --loop-seconds 600 --daily-tail 400 --h1-tail 2400 --top-n 40 >> `"runtime\logs\futures_radar_order_loop.log`" 2>> `"runtime\logs\futures_radar_order_loop_err.log`""
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root } | Out-Null

Start-Sleep -Seconds 2
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*fengji_radar_order_loop.py*" } |
    ForEach-Object { "PID=$($_.ProcessId) CMD=$($_.CommandLine)" }
