# Persistent API starter for Windows Task Scheduler (survives SSH disconnect).
param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$logDir = Join-Path $Root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "fengji_api_stdout.log"
$stderr = Join-Path $logDir "fengji_api_stderr.log"
$pidFile = Join-Path $logDir "fengji_api.pid"
$envFile = Join-Path $Root "runtime\secrets\fengji_api.env"

if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        if ($line -match "^([^=]+)=(.*)$") {
            Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim()
        }
    }
}

$env:PYTHONPATH = "src;packages/fengji_core;services"

function Stop-PortListener([int]$TargetPort) {
    $conns = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        if ($conn.OwningProcess -gt 0) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Stop-PortListener -TargetPort $Port
if (Test-Path -LiteralPath $pidFile) {
    $oldPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
    if ($oldPid) { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

$proc = Start-Process -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "services.api.main:app", "--host", $BindHost, "--port", "$Port"
) -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr

Set-Content -LiteralPath $pidFile -Value $proc.Id -Encoding ASCII
Write-Host "FengJi API service pid=$($proc.Id)"
