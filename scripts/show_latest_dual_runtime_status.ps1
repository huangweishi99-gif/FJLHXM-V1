param(
    [string]$LogRoot = "",
    [int]$MaxAgeMinutes = 120
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $LogRoot) {
    $LogRoot = Join-Path $Root "runtime\logs\dual_runtime_check"
}

if ($MaxAgeMinutes -le 0) {
    Write-Output "ERROR: MaxAgeMinutes must be greater than zero."
    exit 2
}

$summaryFiles = @()
if (Test-Path -LiteralPath $LogRoot) {
    $summaryFiles = @(
        Get-ChildItem -LiteralPath $LogRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $candidate = Join-Path $_.FullName "SUMMARY.md"
                if (Test-Path -LiteralPath $candidate) {
                    Get-Item -LiteralPath $candidate
                }
            } |
            Sort-Object LastWriteTimeUtc -Descending
    )
}

if ($summaryFiles.Count -eq 0) {
    Write-Output "ERROR: No dual-server runtime summary found under $LogRoot"
    exit 2
}

$latest = $summaryFiles[0]
$content = Get-Content -LiteralPath $latest.FullName -Raw -Encoding UTF8
$statusMatch = [regex]::Match($content, '(?m)^- status:\s*(PASS|FAIL)\s*$')
if (-not $statusMatch.Success) {
    Write-Output "ERROR: Latest summary has no valid PASS/FAIL status: $($latest.FullName)"
    exit 2
}

function Get-ExitCodeValue {
    param(
        [string]$Name,
        [string]$Text
    )

    $match = [regex]::Match($Text, "(?m)^- $Name`: exit_code=(-?\d+),")
    if ($match.Success) {
        return $match.Groups[1].Value
    }
    return "not_checked"
}

$status = $statusMatch.Groups[1].Value
$age = [DateTime]::UtcNow - $latest.LastWriteTimeUtc
$ageMinutes = [Math]::Round($age.TotalMinutes, 1)
$freshness = if ($age.TotalMinutes -le $MaxAgeMinutes) { "FRESH" } else { "STALE" }

Write-Output "latest_summary=$($latest.FullName)"
Write-Output "status=$status"
Write-Output "freshness=$freshness"
Write-Output "age_minutes=$ageMinutes"
Write-Output "max_age_minutes=$MaxAgeMinutes"
Write-Output "domestic_exit_code=$(Get-ExitCodeValue -Name 'domestic' -Text $content)"
Write-Output "overseas_exit_code=$(Get-ExitCodeValue -Name 'overseas' -Text $content)"

if ($freshness -eq "STALE") {
    exit 3
}
if ($status -eq "FAIL") {
    exit 1
}
exit 0
