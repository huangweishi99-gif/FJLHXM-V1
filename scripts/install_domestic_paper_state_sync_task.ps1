param(
    [string]$TaskName = "FengJiDomesticPaperStateSync",
    [int]$IntervalMinutes = 1
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$syncScript = Join-Path $root "scripts\sync_domestic_paper_state.ps1"
if (-not (Test-Path -LiteralPath $syncScript)) {
    throw "sync script not found: $syncScript"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$syncScript`""
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Sync domestic FengJi paper_state to local runtime for Web monitor." `
    -Force | Out-Host

Write-Host "installed task: $TaskName every $IntervalMinutes minute(s)"
Write-Host "script: $syncScript"
