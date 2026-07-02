# Stop SSH reverse tunnel: remote 15432 -> local Docker PG 5432.
param(
    [string]$SshAlias = "domestic-quant",
    [int]$LocalPgPort = 5432,
    [int]$RemotePgTunnelPort = 15432
)

$ErrorActionPreference = "Stop"
$procs = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -match "-R\s+${RemotePgTunnelPort}:127\.0\.0\.1:${LocalPgPort}" -and
        $_.CommandLine -match [regex]::Escape($SshAlias)
    }

if (-not $procs) {
    Write-Host "No PG reverse tunnel found ($forward -> $SshAlias)." -ForegroundColor DarkGray
    exit 0
}

foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped ssh pid=$($p.ProcessId)" -ForegroundColor Green
}
Write-Host "PG reverse tunnel stopped ($($procs.Count) process(es))." -ForegroundColor Green
