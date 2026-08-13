param(
    [string]$TaskName = "FengJiUserPaperExecutionJob",
    [int]$IntervalMinutes = 1
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$job = Join-Path $root "scripts\run_user_paper_execution_job.py"
if (-not (Test-Path -LiteralPath $job)) {
    throw "job script not found: $job"
}

$logDir = Join-Path $root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "user_paper_execution_job.log"

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command `"& python '$job' *>> '$logFile'`""
$action = New-FengJiHiddenTaskAction -LauncherPath $launcher
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
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
    -Description "V1.1 per-user CRYPTO paper execution job (standard/pro, plan-rate-limited, every $IntervalMinutes min)." `
    -Force | Out-Host

Write-Host "installed task: $TaskName every $IntervalMinutes minute(s)"
Write-Host "job: $job"
Write-Host "launcher: $launcher"
Write-Host "log: $logFile"
