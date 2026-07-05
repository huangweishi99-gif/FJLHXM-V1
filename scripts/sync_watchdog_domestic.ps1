# Sync watchdog + data-pump guard scripts to domestic server (minimal deploy).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RemoteHost = "domestic-quant"
$RemoteRoot = "C:/Users/Administrator/quant_futures"

$files = @(
    "scripts/watchdog_domestic.ps1",
    "scripts/ensure_single_data_manager.ps1",
    "scripts/check_domestic_status.ps1",
    "scripts/restart_domestic_data_manager.ps1",
    "scripts/verify_pg_sc_15m_csv.ps1",
    "scripts/probe_domestic_futures_15m.py",
    "scripts/install_watchdog_domestic_task.ps1"
)

Write-Host "Sync watchdog guard scripts to domestic ..." -ForegroundColor Cyan
foreach ($rel in $files) {
    $local = Join-Path $Root ($rel -replace "/", "\")
    if (-not (Test-Path -LiteralPath $local)) { throw "Missing: $local" }
    $remotePath = "$RemoteRoot/$($rel -replace '\\','/')"
    scp -o BatchMode=yes -o ConnectTimeout=20 "$local" "${RemoteHost}:$remotePath"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel -> $remotePath" }
    Write-Host "  OK $rel" -ForegroundColor DarkGray
}

Write-Host "Run ensure_single_data_manager + clear stale alert + verify ..." -ForegroundColor Cyan
$remoteScript = @'
Set-Location C:\Users\Administrator\quant_futures
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\ensure_single_data_manager.ps1
Remove-Item runtime\watchdog\data_stale.alert -ErrorAction SilentlyContinue
$cnt = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "data_manager_futures\.py" }).Count
Write-Host "data_manager count=$cnt"
$hasDedupe = Select-String -Path scripts\watchdog_domestic.ps1 -Pattern "Ensure-SingleDataManager" -Quiet
Write-Host "watchdog dedupe=$hasDedupe"
Get-ChildItem data\15m\*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1 Name, LastWriteTime
'@
$enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
ssh -o BatchMode=yes $RemoteHost "powershell -NoProfile -EncodedCommand $enc"

Write-Host "`nWatchdog guard sync done." -ForegroundColor Green
