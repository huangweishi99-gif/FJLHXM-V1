$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "fengji_futures_pending_order_monitor" }
foreach ($p in $procs) {
    $flag = if ($p.CommandLine -match "feishu-webhook\s+`"https://") { "HAS_WEBHOOK_IN_CMDLINE" } else { "OK_NO_WEBHOOK_IN_CMDLINE" }
    Write-Output "PID=$($p.ProcessId) $flag"
}
$envFile = "C:\Users\Administrator\quant_futures\runtime\feishu_webhook.env"
Write-Output ("feishu_webhook.env=" + (Test-Path $envFile))
