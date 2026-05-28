$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "01-08|模拟实盘" }
foreach ($p in $procs) {
    if ($p.CommandLine -notmatch "\.py") { continue }
    $flag = if ($p.CommandLine -match "feishu-webhook\s+`"https://") { "WARN_CMDLINE" } else { "OK" }
    Write-Host "PID=$($p.ProcessId) $flag"
}
$log = "C:\Users\Administrator\quant_futures\runtime\logs\paper_futures_run.log"
if (Test-Path $log) {
    Write-Host "--- paper log tail ---"
    Get-Content $log -Tail 8 -Encoding UTF8
}
