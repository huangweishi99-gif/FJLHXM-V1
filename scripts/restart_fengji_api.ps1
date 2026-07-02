# Server-side: load env, restart uvicorn for FengJi Web API (W17-prod).
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
} else {
    Write-Host "WARN: missing $envFile — set DATABASE_URL and FENGJI_JWT_SECRET before production use" -ForegroundColor Yellow
}

if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = "src;packages/fengji_core;services"
}

if (-not $env:FENGJI_JWT_SECRET -and -not $env:FENGJI_AUTH_ALLOW_DEV_SECRET) {
    Write-Host "WARN: FENGJI_JWT_SECRET unset; API auth will fail until configured" -ForegroundColor Yellow
}

function Stop-PortListener([int]$TargetPort) {
    $conns = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        if ($conn.OwningProcess -gt 0) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

$taskName = "FengJiApiServer"
$schtasks = Join-Path $env:SystemRoot "System32\schtasks.exe"
$taskExists = $false
if (Test-Path -LiteralPath $schtasks) {
    $q = & $schtasks /Query /TN $taskName /FO LIST 2>$null
    $taskExists = $LASTEXITCODE -eq 0
}

if ($taskExists) {
    Stop-PortListener -TargetPort $Port
    if (Test-Path -LiteralPath $pidFile) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
    & $schtasks /Run /TN $taskName | Out-Null
    Start-Sleep -Seconds 12
    if (-not (Test-Path -LiteralPath $pidFile)) {
        if (Test-Path -LiteralPath $stderr) {
            Get-Content -LiteralPath $stderr -Tail 30
        }
        throw "API pid file not created after schtasks /Run; see $stderr"
    }
    $procId = [int](Get-Content -LiteralPath $pidFile -ErrorAction Stop)
    Write-Host "FengJi API started via $taskName pid=$procId http://${BindHost}:$Port/api/v1/health" -ForegroundColor Green
    return
}

Stop-PortListener -TargetPort $Port
if (Test-Path -LiteralPath $pidFile) {
    $oldPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
    if ($oldPid) {
        Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

# Detach from SSH session (sshd may kill direct child processes on disconnect).
$launchPs1 = Join-Path $Root "runtime\logs\_launch_fengji_api.ps1"
$launchBody = @"
`$ErrorActionPreference = 'Stop'
Set-Location '$Root'
if (Test-Path -LiteralPath '$envFile') {
    Get-Content -LiteralPath '$envFile' -Encoding UTF8 | ForEach-Object {
        `$line = `$_.Trim()
        if (-not `$line -or `$line.StartsWith('#')) { return }
        if (`$line -match '^([^=]+)=(.*)$') {
            Set-Item -Path ('env:' + `$matches[1].Trim()) -Value `$matches[2].Trim()
        }
    }
}
`$env:PYTHONPATH = 'src;packages/fengji_core;services'
`$psi = New-Object System.Diagnostics.ProcessStartInfo
`$psi.FileName = 'python'
`$psi.Arguments = '-m uvicorn services.api.main:app --host $BindHost --port $Port'
`$psi.WorkingDirectory = '$Root'
`$psi.UseShellExecute = `$true
`$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
`$proc = [System.Diagnostics.Process]::Start(`$psi)
if (`$proc) {
    Set-Content -LiteralPath '$pidFile' -Value `$proc.Id -Encoding ASCII
}
"@
Set-Content -LiteralPath $launchPs1 -Value $launchBody -Encoding UTF8

Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launchPs1
) -WindowStyle Hidden | Out-Null

Start-Sleep -Seconds 12
if (-not (Test-Path -LiteralPath $pidFile)) {
    if (Test-Path -LiteralPath $stderr) {
        Get-Content -LiteralPath $stderr -Tail 30
    }
    throw "API pid file not created; see $stderr"
}

$procId = [int](Get-Content -LiteralPath $pidFile -ErrorAction Stop)
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
if (-not $proc) {
    if (Test-Path -LiteralPath $stderr) {
        Get-Content -LiteralPath $stderr -Tail 30
    }
    throw "uvicorn exited early (pid=$procId); see $stderr"
}

Write-Host "FengJi API started pid=$procId http://${BindHost}:$Port/api/v1/health" -ForegroundColor Green
