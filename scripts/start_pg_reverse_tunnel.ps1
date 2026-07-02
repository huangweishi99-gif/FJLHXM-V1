# Keep SSH reverse tunnel: remote 15432 -> local Docker PG 5432 (for W17 bootstrap only).
param(
    [string]$SshAlias = "domestic-quant",
    [int]$LocalPgPort = 5432,
    [int]$RemotePgTunnelPort = 15432
)

$ErrorActionPreference = "Stop"
$forward = "${RemotePgTunnelPort}:127.0.0.1:${LocalPgPort}"
$pattern = $forward.Replace(".", "\.")

$existing = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$pattern*" }
if ($existing) {
    Write-Host "PG tunnel already running pid=$($existing.ProcessId)" -ForegroundColor DarkGray
    exit 0
}

Start-Process -FilePath "ssh" -ArgumentList @(
    "-o", "BatchMode=yes",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=6",
    "-o", "ExitOnForwardFailure=yes",
    "-N",
    "-R", $forward,
    $SshAlias
) -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "Started PG reverse tunnel $SshAlias :${RemotePgTunnelPort} -> 127.0.0.1:${LocalPgPort}" -ForegroundColor Green
Write-Host "Leave this ssh process running while remote API uses the tunnel." -ForegroundColor Yellow
