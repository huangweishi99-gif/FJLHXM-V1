param(
    [string]$TaskName = "FengJiPaperStateSyncAndPush",
    [int]$IntervalMinutes = 2
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "fengji_task_hidden.ps1")
$orchestrator = Join-Path $root "scripts\sync_and_push_paper_state_for_web.ps1"
if (-not (Test-Path -LiteralPath $orchestrator)) {
    throw "orchestrator not found: $orchestrator"
}

$legacyTasks = @(
    "FengJiDomesticPaperStateSync",
    "FengJiOverseasPaperStateSync"
)
foreach ($legacy in $legacyTasks) {
    $existing = Get-ScheduledTask -TaskName $legacy -ErrorAction SilentlyContinue
    if ($existing) {
        Disable-ScheduledTask -TaskName $legacy | Out-Null
        Write-Host "disabled legacy task: $legacy"
    }
}

$launcher = New-FengJiHiddenVbsLauncher `
    -Name $TaskName `
    -Command "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$orchestrator`" -SkipVerify"
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
    -Description "Sync domestic+overseas paper_state locally, push to domestic-quant API runtime (hidden, every $IntervalMinutes min)." `
    -Force | Out-Host

Write-Host "installed task: $TaskName every $IntervalMinutes minute(s)"
Write-Host "orchestrator: $orchestrator"
Write-Host "launcher: $launcher"
Write-Host "logs: runtime/logs/domestic_paper_state_sync.log · overseas_paper_state_sync.log · push_paper_state_to_domestic_api.log"
