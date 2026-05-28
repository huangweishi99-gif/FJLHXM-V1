# 国内模拟盘运行时重启（2核4G：雷达周期 600s，K 线 tail 收敛，飞书 webhook 不落命令行）
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
. (Join-Path $PSScriptRoot "load_feishu_webhook.ps1")
$hook = Get-FeishuWebhook -Root $root
if ($hook) { $env:FENGJI_FEISHU_WEBHOOK = $hook }

Set-Location $root
New-Item -ItemType Directory -Force -Path runtime\logs | Out-Null

$patterns = "峰极总定式01-08国内期货A股模拟实盘|模拟实盘|fengji_radar_order_loop|fengji_futures_pending_order_monitor"
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $patterns } | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Seconds 2

$paper = (Get-ChildItem -File -Filter "*模拟实盘.py" | Select-Object -First 1).FullName
if (-not $paper) { throw "Domestic paper script (*模拟实盘.py) not found under $root" }

$symbols = "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC"
$hookSet = if ($hook) { "set FENGJI_FEISHU_WEBHOOK=$hook&& " } else { "" }
$prefix = "cmd.exe /d /c cd /d `"$root`" && set PYTHONPATH=src;packages/fengji_core&& set FENGJI_MARKET=futures&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& $hookSet"
$stateFile = "runtime\fengji_pending_orders\futures_pending_state.json"

function New-DetachedProcess([string]$cmd) {
    $result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root }
    "CREATE ReturnValue=$($result.ReturnValue) PID=$($result.ProcessId)"
}

New-DetachedProcess ($prefix + "`"$py`" -u `"$paper`" >> `"runtime\logs\paper_futures_run.log`" 2>> `"runtime\logs\paper_futures_err.log`"")
New-DetachedProcess ($prefix + "`"$py`" -u `"src\fengji_radar_order_loop.py`" --data-dir data --symbols `"$symbols`" --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state `"$stateFile`" --include-triggered --loop-seconds 600 --daily-tail 400 --h1-tail 2400 --top-n 40 >> `"runtime\logs\futures_radar_order_loop.log`" 2>> `"runtime\logs\futures_radar_order_loop_err.log`"")
New-DetachedProcess ($prefix + "`"$py`" -u `"src\fengji_futures_pending_order_monitor.py`" --orders-file runtime\fengji_pending_orders\pending_orders.json --out-dir runtime\fengji_pending_orders --state-file runtime\fengji_pending_orders\futures_pending_state.json --paper-state-file runtime\fengji_futures\state_futures_v2.json --trade-csv runtime\fengji_futures\trades_futures_astock.csv --data-dir data --price-timeframes 15m,1h,1d --loop-seconds 5 --max-ds01-entries 3 --max-open-positions-per-symbol 3 --lots 1 --enforce-valid-until >> `"runtime\logs\futures_pending_order_monitor.log`" 2>> `"runtime\logs\futures_pending_order_monitor_err.log`"")

Start-Sleep -Seconds 5
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "data_manager_futures|模拟实盘|fengji_radar_order_loop|fengji_futures_pending_order_monitor" } | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -match "feishu-webhook\s+`"https://") {
        "WARN PID=$($_.ProcessId) still has webhook in command line — rotate webhook and redeploy"
    } else {
        "PID=$($_.ProcessId) OK"
    }
}
