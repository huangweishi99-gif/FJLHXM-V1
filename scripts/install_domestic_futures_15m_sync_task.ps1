param(
    [string]$TaskName = "FengJiDomesticFutures15mSync",
    [string[]]$DailyAt = @("07:30", "19:30")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$runner = Join-Path $root "scripts\run_sync_domestic_futures_15m_for_context.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "runner not found: $runner"
}

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command `"`$env:FENGJI_SYNC_QUIET='1'; & '$runner'`""
$action = New-FengJiHiddenTaskAction -LauncherPath $launcher
$triggers = @()
foreach ($at in $DailyAt) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $at
}
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -Hidden

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Description "Sync domestic futures 15m CSV from server to data/futures/15m for context backfill." `
    -Force | Out-Host

Write-Host "installed hidden task: $TaskName at $($DailyAt -join ', ') daily"
Write-Host "runner: $runner"
Write-Host "launcher: $launcher"
Write-Host "log: runtime/logs/domestic_futures_15m_sync.log"
