# 从本机 SSH 调用国内服务器运行态检查（委托 check_domestic_status.ps1，避免 EncodedCommand 转义问题）
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures"
)

$ErrorActionPreference = "Stop"
Write-Host "Connecting $SshHost ..." -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=25 $SshHost "powershell -NoProfile -File $RemoteRoot/scripts/check_domestic_status.ps1"

Write-Host "`n===== PG/SC 15m ACCEPTANCE =====" -ForegroundColor Cyan
ssh -o BatchMode=yes -o ConnectTimeout=25 $SshHost "powershell -NoProfile -File $RemoteRoot/scripts/verify_pg_sc_15m_csv.ps1"
$pgExit = $LASTEXITCODE
if ($pgExit -ge 2) { exit $pgExit }

Write-Host "`n===== EXTRA PROCESSES =====" -ForegroundColor Cyan
$remoteExtra = @'
Set-Location C:/Users/Administrator/quant_futures
$radar = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'fengji_radar_order_loop\.py' })
$pending = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'fengji_futures_pending_order_monitor\.py' })
Write-Host ("radar python count=" + $radar.Count + " (expect 1)")
Write-Host ("pending python count=" + $pending.Count + " (expect 1)")
if ($radar.Count -gt 1) { Write-Host "WARN duplicate radar — run restart_domestic_radar_loop.ps1" }
if ($pending.Count -gt 1) { Write-Host "WARN duplicate pending monitor" }
$radar | ForEach-Object { Write-Output ("radar PID=" + $_.ProcessId) }
$pending | ForEach-Object { Write-Output ("pending PID=" + $_.ProcessId) }
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteExtra))
ssh -o BatchMode=yes -o ConnectTimeout=25 $SshHost "powershell -NoProfile -EncodedCommand $encoded"
exit $pgExit
