# Build read-only watchlist runtime file cache for all pending_runtime users.
# Safe: no paper_state writes, no order triggers. For local dev or optional scheduled task.
param(
    [string]$Python = "",
    [string]$Status = "pending_runtime",
    [int]$Limit = 100,
    [int]$LimitUsers = 200,
    [switch]$NoSignalPreview,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if (-not $Python) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "python"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -eq "python" -or (Test-Path -LiteralPath $candidate)) {
            $Python = $candidate
            break
        }
    }
}

$argsList = @(
    "scripts/run_watchlist_runtime_job.py",
    "--all-users",
    "--status", $Status,
    "--limit", "$Limit",
    "--limit-users", "$LimitUsers"
)
if ($NoSignalPreview) { $argsList += "--no-signal-preview" }
if ($DryRun) { $argsList += "--dry-run" }

& $Python @argsList
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
