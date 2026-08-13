param(
    [string]$TaskName = "FengJiNew10FillWatch",
    [int]$IntervalMinutes = 15
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$runner = Join-Path $root "scripts\run_new10_fill_watch.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "runner not found: $runner"
}

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command `"`$env:FENGJI_NEW10_WATCH_QUIET='1'; & '$runner' -EmitSandbox`""
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
    -Description "Watch overseas new-10 crypto fills; auto sandbox on new open_position (hidden, every $IntervalMinutes min)." `
    -Force | Out-Host

Write-Host "installed task: $TaskName every $IntervalMinutes minute(s)"
Write-Host "runner: $runner"
Write-Host "launcher: $launcher"
Write-Host "log: runtime/logs/new10_fill_watch.log"
Write-Host "state: runtime/new10_fill_watch_state.json"
Write-Host "output: results/new10_fill_watch/"
