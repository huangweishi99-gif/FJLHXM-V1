# Run ON domestic server: 诊断期货挂单监控进程与启动参数来源
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== PROCS (monitor/radar/paper/cmd wrappers) ==="
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and ($_.CommandLine -match "fengji_futures_pending_order_monitor|run_futures_pending_monitor|fengji_radar_order_loop")
})
foreach ($p in $procs) {
    $cmd = $p.CommandLine
    if ($cmd.Length -gt 260) { $cmd = $cmd.Substring(0, 260) + "..." }
    Write-Host ("PID=" + $p.ProcessId + " NAME=" + $p.Name + " START=" + $p.CreationDate)
    Write-Host ("  CMD=" + $cmd)
}
Write-Host ("total procs: " + $procs.Count)

Write-Host "`n=== SOURCE ARG SUPPORT ==="
$src = Join-Path $root "src\fengji_futures_pending_order_monitor.py"
if (Test-Path -LiteralPath $src) {
    $hit = Select-String -LiteralPath $src -Pattern "os-state-dir" -ErrorAction SilentlyContinue
    if ($hit) { $hit | ForEach-Object { Write-Host ("L" + $_.LineNumber + ": " + $_.Line.Trim()) } }
    else { Write-Host "MISSING --os-state-dir in src (old code)" }
    Write-Host ("src mtime: " + (Get-Item -LiteralPath $src).LastWriteTime)
} else { Write-Host "src missing" }

Write-Host "`n=== LAUNCHERS CONTAINING --os-state-dir ==="
foreach ($f in @("scripts\run_futures_pending_monitor.ps1", "scripts\run_futures_pending_monitor.cmd", "scripts\watchdog_domestic.ps1", "scripts\restart_domestic_pending_only.ps1", "scripts\restart_domestic_futures_runtime.ps1")) {
    $p = Join-Path $root $f
    if (Test-Path -LiteralPath $p) {
        $h = Select-String -LiteralPath $p -Pattern "os-state-dir" -ErrorAction SilentlyContinue
        $flag = if ($h) { "HAS" } else { "none" }
        Write-Host ("$f : $flag  mtime=" + (Get-Item -LiteralPath $p).LastWriteTime)
    } else {
        Write-Host "$f : missing"
    }
}

Write-Host "`n=== LOG TAIL ==="
$log = Join-Path $root "runtime\logs\futures_pending_order_monitor.log"
if (Test-Path $log) { Get-Content $log -Tail 5 -Encoding UTF8 } else { Write-Host "no log" }
Write-Host "=== ERR TAIL ==="
$err = Join-Path $root "runtime\logs\futures_pending_order_monitor_err.log"
if (Test-Path $err) { Get-Content $err -Tail 5 -Encoding UTF8 } else { Write-Host "no err log" }

Write-Host "`n=== OPS STATS ==="
$statsDir = Join-Path $root "runtime\fengji_ops_stats"
if (Test-Path $statsDir) { Get-ChildItem $statsDir | ForEach-Object { Write-Host ($_.Name + " " + $_.Length + " " + $_.LastWriteTime) } }
else { Write-Host "no ops stats dir" }
