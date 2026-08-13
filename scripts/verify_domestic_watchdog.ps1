# Post-deploy verification for domestic watchdog + data_manager (run ON server).
$ErrorActionPreference = "Continue"
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
$hb = Join-Path $root "runtime\logs\data_manager_heartbeat.txt"
$HeartbeatMaxAgeSec = 420
$fail = 0

Write-Host "=== WATCHDOG TASK ==="
$t = schtasks /Query /TN FengJiDomesticWatchdog /FO LIST /V 2>$null
if ($t) { $t | Select-String "Run As User|Status|Task To Run" } else { Write-Host "FAIL: task missing"; $fail++ }

Write-Host "`n=== DATA MANAGER ==="
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "python" -and $_.CommandLine -and ($_.CommandLine -match "data_manager_futures\.py")
})
Write-Host "python count=$($procs.Count) (expect 1)"
if ($procs.Count -gt 1) { $fail++ }
if (Test-Path $hb) {
    $age = [int](((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds)
    Write-Host "heartbeat age=${age}s: $(Get-Content $hb -TotalCount 1)"
    if ($age -gt $HeartbeatMaxAgeSec) { Write-Host "WARN heartbeat stale"; $fail++ }
} else {
    Write-Host "FAIL: no heartbeat file"; $fail++
}

Write-Host "`n=== PAPER / RADAR / PENDING (must stay up) ==="
function Count-Procs($pat) {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match "python" -and $_.CommandLine -and ($_.CommandLine -match $pat)
    }).Count
}
$paper = Count-Procs "01-08"
$radar = Count-Procs "fengji_radar_order_loop"
$pending = Count-Procs "fengji_futures_pending_order_monitor"
Write-Host "paper=$paper radar=$radar pending=$pending"
if ($paper -lt 1 -or $radar -lt 1 -or $pending -lt 1) { Write-Host "WARN core runtime missing a process"; $fail++ }

Write-Host "`n=== WATCHDOG DRY RUN ==="
Remove-Item runtime\watchdog\proc_data_manager.alert -ErrorAction SilentlyContinue
$out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\watchdog_domestic.ps1 2>&1
$out | Select-Object -Last 5
if ($out -match "data_manager down") { Write-Host "FAIL: watchdog still thinks data_manager down"; $fail++ }
if ($out -match "ALERT\[proc_data_manager\]") { Write-Host "FAIL: watchdog would alert"; $fail++ }

Write-Host "`n=== RESULT ==="
if ($fail -eq 0) { Write-Host "PASS all checks"; exit 0 }
Write-Host "FAIL count=$fail"; exit 1
