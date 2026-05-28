# 仅重启国内挂单监控（应用 webhook 脱敏，不影响模拟盘/雷达）
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "fengji_futures_pending_order_monitor" } | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot "run_futures_pending_monitor.ps1")
Start-Sleep -Seconds 2
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "fengji_futures_pending_order_monitor" } | ForEach-Object {
    if ($_.CommandLine -match "feishu-webhook\s+`"https://") {
        Write-Host "WARN: webhook still visible in command line — check runtime/feishu_webhook.env"
    } else {
        Write-Host "Pending monitor PID=$($_.ProcessId) started (webhook not in cmdline)"
    }
}
