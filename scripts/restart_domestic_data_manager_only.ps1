# Restart ONLY data_manager (paper/radar/pending untouched).
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
Remove-Item (Join-Path $root "runtime\watchdog\data_manager_start.lock") -ErrorAction SilentlyContinue
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "python" -and $_.CommandLine -and ($_.CommandLine -match "data_manager_futures\.py")
})
Write-Host "stopping $($procs.Count) data_manager process(es)..."
foreach ($p in $procs) {
    try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Host "stopped PID=$($p.ProcessId)" } catch {}
}
Start-Sleep -Seconds 3
& (Join-Path $root "scripts\ensure_single_data_manager.ps1")
