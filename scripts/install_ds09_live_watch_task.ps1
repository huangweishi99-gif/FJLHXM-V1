param(
    [string]$TaskName = "FengJiDs09LiveWatch",
    [int]$IntervalMinutes = 15
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$runner = Join-Path $root "scripts\run_ds09_live_watch.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "runner not found: $runner"
}

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command `"`$env:FENGJI_DS09_WATCH_QUIET='1'; & '$runner'`""
$action = New-FengJiHiddenTaskAction -LauncherPath $launcher
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -Hidden

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Scan crypto radar for new DS09 rows and emit session sandbox charts (hidden, every $IntervalMinutes min)." `
    -Force | Out-Host

Write-Host "installed task: $TaskName every $IntervalMinutes minute(s)"
Write-Host "runner: $runner"
Write-Host "launcher: $launcher"
Write-Host "log: runtime/logs/ds09_live_watch.log"
Write-Host "state: runtime/ds09_live_watch_state.json"
Write-Host "output: results/ds09_live_watch/"
