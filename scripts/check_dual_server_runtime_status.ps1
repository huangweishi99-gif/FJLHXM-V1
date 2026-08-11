param(
    [switch]$SkipDomestic,
    [switch]$SkipOverseas,
    [string]$DomesticSshHost = "domestic-quant",
    [string]$DomesticRemoteRoot = "C:/Users/Administrator/quant_futures",
    [string]$OverseasSshHost = "overseas-quant",
    [string]$OverseasRemoteDir = "/home/ubuntu/quant_crypto",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$noChecksSelected = $SkipDomestic -and $SkipOverseas
if ($noChecksSelected) {
    Write-Host "ERROR: No runtime checks selected." -ForegroundColor Red
    exit 2
}

$Ts = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $OutputDir) {
    $OutputDir = Join-Path $Root ("runtime\logs\dual_runtime_check\" + $Ts)
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Invoke-RuntimeCheck {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [string[]]$Arguments,
        [string]$LogPath
    )

    Write-Host "===== $Name runtime check =====" -ForegroundColor Cyan
    $commandArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ScriptPath) + $Arguments
    $output = & powershell @commandArgs 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }

    $output | Set-Content -LiteralPath $LogPath -Encoding UTF8
    $output | ForEach-Object { Write-Host $_ }
    Write-Host "===== $Name exit_code=$exitCode log=$LogPath =====" -ForegroundColor Cyan

    return [pscustomobject]@{
        name = $Name
        exit_code = [int]$exitCode
        log = $LogPath
    }
}

$results = @()

if (-not $SkipDomestic) {
    $domesticLog = Join-Path $OutputDir "domestic_runtime.log"
    $results += Invoke-RuntimeCheck `
        -Name "domestic" `
        -ScriptPath (Join-Path $Root "scripts\check_domestic_runtime_remote.ps1") `
        -Arguments @("-SshHost", $DomesticSshHost, "-RemoteRoot", $DomesticRemoteRoot) `
        -LogPath $domesticLog
}

if (-not $SkipOverseas) {
    $overseasLog = Join-Path $OutputDir "overseas_runtime.log"
    $results += Invoke-RuntimeCheck `
        -Name "overseas" `
        -ScriptPath (Join-Path $Root "scripts\check_overseas_runtime_status.ps1") `
        -Arguments @("-SshHost", $OverseasSshHost, "-RemoteDir", $OverseasRemoteDir) `
        -LogPath $overseasLog
}

if ($results.Count -eq 0) {
    Write-Host "ERROR: No runtime checks selected." -ForegroundColor Red
    exit 2
}

$failed = @($results | Where-Object { $_.exit_code -ne 0 })
$status = if ($failed.Count -eq 0) { "PASS" } else { "FAIL" }
$summaryPath = Join-Path $OutputDir "SUMMARY.md"
$summaryLines = @(
    "# Dual Server Runtime Check - $Ts",
    "",
    "- status: $status",
    "- output_dir: $OutputDir",
    ""
)

foreach ($result in $results) {
    $summaryLines += "- $($result.name): exit_code=$($result.exit_code), log=$($result.log)"
}

$summaryLines | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "===== summary =====" -ForegroundColor Green
Get-Content -LiteralPath $summaryPath -Encoding UTF8

if ($failed.Count -gt 0) {
    exit 1
}
exit 0
