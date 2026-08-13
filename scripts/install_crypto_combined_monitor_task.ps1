param(
    [string]$TaskName = "FengJiCryptoCombinedMonitor",
    [int]$IntervalMinutes = 30
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$runner = Join-Path $root "scripts\run_crypto_combined_monitor.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "runner not found: $runner"
}

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command `"`$env:FENGJI_CRYPTO_COMBINED_MONITOR_QUIET='1'; & '$runner'`""
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
    -Description "Plan A5: DS01-DS09 crypto combined monitor (observe-only, cache-first, every $IntervalMinutes min)." `
    -Force | Out-Host

Write-Host "installed task: $TaskName every $IntervalMinutes minute(s)"
Write-Host "runner: $runner"
Write-Host "launcher: $launcher"
Write-Host "log: runtime/logs/crypto_combined_monitor.log"
Write-Host "latest: results/crypto_combined_monitor/latest_combined_monitor_signals.csv"
