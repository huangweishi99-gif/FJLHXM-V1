# 国内期货挂单监控（webhook 从 runtime/feishu_webhook.env 或环境变量读取，不写进命令行）
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "load_feishu_webhook.ps1")
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$hook = Get-FeishuWebhook -Root $root
Set-Location $root
New-Item -ItemType Directory -Force -Path runtime\logs | Out-Null
$env:PYTHONPATH = "src;packages/fengji_core"
$env:FENGJI_MARKET = "futures"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
if ($hook) { $env:FENGJI_FEISHU_WEBHOOK = $hook }

$args = @(
    "-u", "src\fengji_futures_pending_order_monitor.py",
    "--orders-file", "runtime\fengji_pending_orders\pending_orders.json",
    "--out-dir", "runtime\fengji_pending_orders",
    "--state-file", "runtime\fengji_pending_orders\futures_pending_state.json",
    "--paper-state-file", "runtime\fengji_futures\state_futures_v2.json",
    "--trade-csv", "runtime\fengji_futures\trades_futures_astock.csv",
    "--data-dir", "data",
    "--price-timeframes", "15m,1h,1d",
    "--loop-seconds", "5",
    "--max-ds01-entries", "3",
    "--max-open-positions-per-symbol", "3",
    "--lots", "1",
    "--enforce-valid-until"
)
$logOut = Join-Path $root "runtime\logs\futures_pending_order_monitor.log"
$logErr = Join-Path $root "runtime\logs\futures_pending_order_monitor_err.log"
$argLine = ($args | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join ' '
$pp = "src;packages/fengji_core"
$cmd = "cmd.exe /d /c cd /d `"$root`" && set `"PYTHONPATH=$pp`"&& set FENGJI_MARKET=futures&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& `"$py`" $argLine >> `"$logOut`" 2>> `"$logErr`""
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root } | Out-Null
