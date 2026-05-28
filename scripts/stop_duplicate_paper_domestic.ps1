$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "01-08" -and $_.CommandLine -match "python" })
if ($procs.Count -le 1) { Write-Host "single paper OK"; exit 0 }
$keep = $procs | Sort-Object CreationDate | Select-Object -Last 1
foreach ($p in $procs) {
    if ($p.ProcessId -eq $keep.ProcessId) { continue }
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "stopped old paper PID=$($p.ProcessId)"
}
Write-Host "kept paper PID=$($keep.ProcessId)"
