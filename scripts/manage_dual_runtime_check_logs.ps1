param(
    [string]$LogRoot = "",
    [int]$RetentionDays = 14,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $LogRoot) {
    $LogRoot = Join-Path $Root "runtime\logs\dual_runtime_check"
}

if ($RetentionDays -le 0) {
    Write-Output "ERROR: RetentionDays must be greater than zero."
    exit 2
}

$logRootFull = [IO.Path]::GetFullPath($LogRoot)
$mode = if ($Execute) { "EXECUTE" } else { "DRY_RUN" }
Write-Output "log_root=$logRootFull"
Write-Output "mode=$mode"
Write-Output "retention_days=$RetentionDays"

if (-not (Test-Path -LiteralPath $logRootFull)) {
    Write-Output "managed_count=0"
    Write-Output "incomplete_count=0"
    Write-Output "skipped_unmanaged_count=0"
    Write-Output "candidate_count=0"
    Write-Output "deleted_count=0"
    exit 0
}

$rootPrefix = $logRootFull.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$allowedFiles = @("SUMMARY.md", "domestic_runtime.log", "overseas_runtime.log")
$cutoffUtc = [DateTime]::UtcNow.AddDays(-$RetentionDays)
$managed = @()
$skippedUnmanaged = @()

foreach ($directory in @(Get-ChildItem -LiteralPath $logRootFull -Directory -Force)) {
    $directoryFull = [IO.Path]::GetFullPath($directory.FullName)
    $isInsideRoot = $directoryFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)
    $hasManagedName = $directory.Name -match '^\d{8}_\d{6}$'
    $children = @(Get-ChildItem -LiteralPath $directoryFull -Force -ErrorAction SilentlyContinue)
    $hasSubdirectory = @($children | Where-Object { $_.PSIsContainer }).Count -gt 0
    $unknownFiles = @($children | Where-Object { -not $_.PSIsContainer -and $_.Name -notin $allowedFiles })

    if (-not $isInsideRoot -or -not $hasManagedName -or $hasSubdirectory -or $unknownFiles.Count -gt 0) {
        $skippedUnmanaged += $directory
        continue
    }

    $lastWriteUtc = $directory.LastWriteTimeUtc
    foreach ($child in $children) {
        if ($child.LastWriteTimeUtc -gt $lastWriteUtc) {
            $lastWriteUtc = $child.LastWriteTimeUtc
        }
    }

    $sizeBytes = ($children | Where-Object { -not $_.PSIsContainer } | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sizeBytes) {
        $sizeBytes = 0
    }

    $managed += [pscustomobject]@{
        name = $directory.Name
        path = $directoryFull
        last_write_utc = $lastWriteUtc
        size_bytes = [int64]$sizeBytes
        summary = if (Test-Path -LiteralPath (Join-Path $directoryFull "SUMMARY.md")) { "present" } else { "missing" }
    }
}

$candidates = @($managed | Where-Object { $_.last_write_utc -lt $cutoffUtc } | Sort-Object last_write_utc)
$incomplete = @($managed | Where-Object { $_.summary -eq "missing" })

Write-Output "managed_count=$($managed.Count)"
Write-Output "incomplete_count=$($incomplete.Count)"
Write-Output "skipped_unmanaged_count=$($skippedUnmanaged.Count)"
Write-Output "candidate_count=$($candidates.Count)"

foreach ($candidate in $candidates) {
    $ageDays = [Math]::Round(([DateTime]::UtcNow - $candidate.last_write_utc).TotalDays, 1)
    Write-Output "candidate=$($candidate.name),age_days=$ageDays,size_bytes=$($candidate.size_bytes),summary=$($candidate.summary)"
}

$deletedCount = 0
if ($Execute) {
    foreach ($candidate in $candidates) {
        $candidateFull = [IO.Path]::GetFullPath($candidate.path)
        $isSafeTarget = $candidateFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -and
            ([IO.Path]::GetFileName($candidateFull) -match '^\d{8}_\d{6}$')
        if (-not $isSafeTarget) {
            Write-Output "ERROR: Refusing unsafe cleanup target: $candidateFull"
            exit 2
        }
        Remove-Item -LiteralPath $candidateFull -Recurse -Force
        $deletedCount += 1
    }
}

Write-Output "deleted_count=$deletedCount"
exit 0
