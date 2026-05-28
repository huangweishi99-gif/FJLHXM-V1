# 从本机 SSH 调用国内服务器运行态检查
param(
    [string]$SshHost = "domestic-quant"
)

$ErrorActionPreference = "Stop"
$remoteScript = @'
Set-Location C:\Users\Administrator\quant_futures
Write-Host "===== HOST ====="
hostname
Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
Write-Host ""
Write-Host "===== PROCESSES ====="
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "data_manager_futures|fengji_radar_order_loop|fengji_futures_pending|峰极总定式"
} | ForEach-Object { "PID=$($_.ProcessId) $($_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length)))" }
Write-Host ""
Write-Host "===== RADAR / PENDING ====="
if (Test-Path runtime\fengji_radar\radar.json) {
    Get-Item runtime\fengji_radar\radar.json | Select-Object FullName, LastWriteTime, Length
}
if (Test-Path runtime\fengji_pending_orders\pending_orders.json) {
    Get-Item runtime\fengji_pending_orders\pending_orders.json | Select-Object FullName, LastWriteTime, Length
}
Write-Host ""
Write-Host "===== OS STATE ====="
if (Test-Path runtime\fengji_os_state) {
    Get-ChildItem runtime\fengji_os_state -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, LastWriteTime, Length
} else { Write-Host "no_os_state_dir" }
Write-Host ""
Write-Host "===== LC DATA ====="
Get-ChildItem data -Recurse -Filter "LC*.csv" -ErrorAction SilentlyContinue | Select-Object FullName, LastWriteTime, Length
'@

Write-Host "Connecting $SshHost ..." -ForegroundColor Cyan
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
ssh -o BatchMode=yes -o ConnectTimeout=25 $SshHost "powershell -NoProfile -EncodedCommand $encoded"
