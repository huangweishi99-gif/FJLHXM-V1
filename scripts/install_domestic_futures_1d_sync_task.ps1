# Install hidden Windows scheduled task: sync domestic futures 1d CSV -> local Web data/futures/1d
param(
    [string]$TaskName = "FengJiDomesticFutures1dSync",
    [string[]]$DailyAt = @("12:05", "21:05")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$syncScript = Join-Path $root "scripts\run_sync_domestic_futures_1d_for_web.ps1"
if (-not (Test-Path -LiteralPath $syncScript)) {
    throw "sync wrapper not found: $syncScript"
}

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$syncScript`""
$action = New-FengJiHiddenTaskAction -LauncherPath $launcher

$triggers = @()
foreach ($at in $DailyAt) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $at
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -Hidden

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Description "Sync domestic server futures 1d CSV into local Web data/futures/1d (actual main contract only)." `
    -Force | Out-Host

Write-Host "installed hidden task: $TaskName at $($DailyAt -join ', ') daily"
Write-Host "wrapper: $syncScript"
Write-Host "launcher: $launcher"
Write-Host "log: $root\runtime\logs\domestic_futures_1d_sync.log"
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName, State, Description
