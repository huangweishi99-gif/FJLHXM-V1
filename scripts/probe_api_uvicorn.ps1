# Server-side: start API in foreground briefly and hit health (diagnostics).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures",
    [int]$Port = 8000,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
Set-Location $Root

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
python -c "import services.api.main as m; print('import_ok')"

$logDir = Join-Path $Root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "fengji_api_probe_stdout.log"
$stderr = Join-Path $logDir "fengji_api_probe_stderr.log"
if (Test-Path $stdout) { Remove-Item $stdout -Force }
if (Test-Path $stderr) { Remove-Item $stderr -Force }

$proc = Start-Process python -ArgumentList @(
    "-m", "uvicorn", "services.api.main:app", "--host", "127.0.0.1", "--port", "$Port"
) -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden

Start-Sleep -Seconds 6
if ($proc.HasExited) {
    Write-Host "uvicorn_exited code=$($proc.ExitCode)"
    if (Test-Path $stderr) { Get-Content $stderr -Tail 20 }
    exit 1
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 10
    Write-Host "health_ok $($health.status)"
} catch {
    Write-Host "health_fail $($_.Exception.Message)"
    if (Test-Path $stderr) { Get-Content $stderr -Tail 20 }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

if (-not $KeepRunning) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "probe_ok"
if ($KeepRunning) {
    Set-Content -LiteralPath (Join-Path $Root "runtime\logs\fengji_api.pid") -Value $proc.Id -Encoding ASCII
    Write-Host "kept_running pid=$($proc.Id)"
}
