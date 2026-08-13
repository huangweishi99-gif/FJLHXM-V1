# Force restart data_manager when 1d bar stale (weekend CATCHUP)
$root = "C:\Users\Administrator\quant_futures"
Set-Location $root
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"

& $py -c "import data_manager_futures as dm; raise SystemExit(0 if dm.needs_stale_catchup() else 1)"
if ($LASTEXITCODE -ne 0) { Write-Output "catchup_not_needed"; exit 0 }

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "python" -and $_.CommandLine -and ($_.CommandLine -match "data_manager_futures\.py")
} | ForEach-Object {
    Write-Output "stop PID=$($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3
& (Join-Path $root "scripts\ensure_single_data_manager.ps1")
