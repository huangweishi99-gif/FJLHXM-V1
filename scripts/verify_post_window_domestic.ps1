# One-shot post-window domestic verify: chart lines + main contract manifest + data freshness hints.
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [string[]]$ChartSymbols = @("AG", "SC", "NI", "RB", "LC")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$reportPath = Join-Path $root "runtime\logs\post_window_domestic_verify.json"
$failed = 0
$results = [ordered]@{
    checked_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    ssh_host = $SshHost
    steps = @()
}

function Add-Step([string]$Name, [bool]$Ok, [hashtable]$Detail = @{}) {
    $script:results.steps += [ordered]@{
        name = $Name
        ok = $Ok
    } + $Detail
    if (-not $Ok) { $script:failed++ }
}

Write-Host "=== AG chart line ===" -ForegroundColor Cyan
try {
    $agOut = ssh -o BatchMode=yes $SshHost "powershell -NoProfile -ExecutionPolicy Bypass -File $RemoteRoot/scripts/verify_domestic_ag_chart_line.ps1" 2>&1 | Out-String
    Write-Host $agOut
    Add-Step "ag_chart_line" ($LASTEXITCODE -eq 0) @{ output = $agOut.Trim() }
} catch {
    Add-Step "ag_chart_line" $false @{ error = $_.Exception.Message }
}

Write-Host "=== chart lines batch ===" -ForegroundColor Cyan
$symArg = ($ChartSymbols -join ",")
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$batchOut = ssh -o BatchMode=yes $SshHost "powershell -NoProfile -ExecutionPolicy Bypass -File $RemoteRoot/scripts/verify_domestic_chart_lines_batch.ps1 -Symbols $symArg" 2>&1 | Out-String
$batchExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Write-Host $batchOut
Add-Step "chart_lines_batch" ($batchExit -eq 0) @{ symbols = $symArg; output = $batchOut.Trim(); exit_code = $batchExit }

Write-Host "=== main contract manifest ===" -ForegroundColor Cyan
try {
    & (Join-Path $root "scripts\verify_domestic_futures_main_contract.ps1") -SshHost $SshHost -RemoteRoot $RemoteRoot | Out-Host
    Add-Step "main_contract_manifest" ($LASTEXITCODE -eq 0)
} catch {
    Add-Step "main_contract_manifest" $false @{ error = $_.Exception.Message }
}

Write-Host "=== AG CSV tail + data pump ===" -ForegroundColor Cyan
try {
    $agTail = ssh -o BatchMode=yes $SshHost "powershell -NoProfile -Command Get-Content $RemoteRoot/data/1d/AG.csv -Tail 1" 2>&1 | Out-String
    $pumpTail = ssh -o BatchMode=yes $SshHost "powershell -NoProfile -Command Get-Content $RemoteRoot/runtime/logs/data_manager_futures.log -Tail 2" 2>&1 | Out-String
    Write-Host "AG tail: $($agTail.Trim())"
    Write-Host $pumpTail
    $pumpSleeping = $pumpTail -match "不在数据更新时段"
    Add-Step "ag_csv_tail" $true @{ tail = $agTail.Trim(); pump_sleeping = $pumpSleeping; pump_tail = $pumpTail.Trim() }
} catch {
    Add-Step "ag_csv_tail" $false @{ error = $_.Exception.Message }
}

Write-Host "=== backtest trade PnL (SSH tunnel) ===" -ForegroundColor Cyan
try {
    & (Join-Path $root "scripts\verify_domestic_backtest_trade_pnl.ps1") -SshHost $SshHost | Out-Host
    Add-Step "backtest_trade_pnl" ($LASTEXITCODE -eq 0)
} catch {
    Add-Step "backtest_trade_pnl" $false @{ error = $_.Exception.Message }
}

$results.ok = ($failed -eq 0)
$results.failed_steps = $failed
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding UTF8

if ($failed -gt 0) {
    Write-Host "POST_WINDOW_VERIFY_FAIL failed=$failed report=$reportPath" -ForegroundColor Red
    exit 1
}
Write-Host "POST_WINDOW_VERIFY_OK report=$reportPath" -ForegroundColor Green
exit 0
