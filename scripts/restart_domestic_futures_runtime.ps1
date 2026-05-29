# 国内全链路重启：数据泵 + 模拟盘 + 雷达循环 + 期货挂单监控
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
. (Join-Path $PSScriptRoot "load_feishu_webhook.ps1")
. (Join-Path $PSScriptRoot "resolve_domestic_paper.ps1")
$hook = Get-FeishuWebhook -Root $root
if ($hook) { $env:FENGJI_FEISHU_WEBHOOK = $hook }

Set-Location $root
New-Item -ItemType Directory -Force -Path runtime\logs | Out-Null

& (Join-Path $PSScriptRoot "stop_domestic_futures_runtime.ps1")
Start-Sleep -Seconds 1

$paper = Get-DomesticPaperScript -Root $root
Write-Host "paper_script=$paper"

$symbols = "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC"
$hookSet = if ($hook) { "set FENGJI_FEISHU_WEBHOOK=$hook&& " } else { "" }
$prefix = "cmd.exe /d /c cd /d `"$root`" && set `"PYTHONPATH=src;packages/fengji_core`"&& set FENGJI_MARKET=futures&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& $hookSet"
$stateFile = "runtime\fengji_pending_orders\futures_pending_state.json"

function New-DetachedProcess([string]$cmd) {
    $result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root }
    "CREATE ReturnValue=$($result.ReturnValue) PID=$($result.ProcessId)"
}

& (Join-Path $PSScriptRoot "restart_domestic_data_manager.ps1")

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
