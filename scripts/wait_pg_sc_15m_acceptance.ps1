# Poll PG/SC 15m CSV acceptance until OK or timeout (run after ~20:30 night session).
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [int]$IntervalSec = 300,
    [int]$MaxWaitMin = 180
)

$ErrorActionPreference = "Stop"
$deadline = (Get-Date).AddMinutes($MaxWaitMin)
$attempt = 0

Write-Host "Polling verify_pg_sc_15m_csv.ps1 every ${IntervalSec}s until $deadline (max ${MaxWaitMin}min)" -ForegroundColor Cyan

while ((Get-Date) -lt $deadline) {
    $attempt++
    Write-Host "`n--- attempt $attempt @ $(Get-Date -Format 'HH:mm:ss') ---" -ForegroundColor DarkCyan
    ssh -o BatchMode=yes -o ConnectTimeout=25 $SshHost "powershell -NoProfile -File $RemoteRoot/scripts/verify_pg_sc_15m_csv.ps1"
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host "ACCEPTANCE_OK" -ForegroundColor Green
        exit 0
    }
    if ($code -ge 2) {
        Write-Host "ACCEPTANCE_FAIL (hard)" -ForegroundColor Red
        exit $code
    }
    $remain = [int](($deadline - (Get-Date)).TotalSeconds)
    if ($remain -le 0) { break }
    $sleep = [Math]::Min($IntervalSec, $remain)
    Write-Host "PENDING — sleep ${sleep}s (market window may not have written yet)" -ForegroundColor Yellow
    Start-Sleep -Seconds $sleep
}

Write-Host "TIMEOUT: PG/SC still PENDING after ${MaxWaitMin}min" -ForegroundColor Red
exit 1
