# Install domestic watchdog scheduled task as Administrator (NOT SYSTEM).
# SYSTEM cannot reliably see Administrator python CommandLine -> false proc_data_manager alerts.
# Does NOT restart paper/radar/pending.
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$taskName = "FengJiDomesticWatchdog"
$script = Join-Path $root "scripts\watchdog_domestic.ps1"
New-Item -ItemType Directory -Force -Path (Join-Path $root "runtime\logs") | Out-Null
schtasks /Delete /TN $taskName /F 2>$null | Out-Null
$tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""
# /RU Administrator: same account as data_manager / paper / radar (no cross-session blind spot)
schtasks /Create /TN $taskName /TR $tr /SC MINUTE /MO 1 /RU Administrator /RL HIGHEST /F | Out-Null
Write-Host "Task installed: $taskName (Administrator)"
schtasks /Query /TN $taskName /FO LIST /V | Select-String "TaskName|Status|Next Run|Run As User|Task To Run"
