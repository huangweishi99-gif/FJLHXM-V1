# Install Windows scheduled task to start FengJi Web API (Administrator).
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$taskName = "FengJiApiServer"
$script = Join-Path $root "scripts\start_fengji_api_service.ps1"
$schtasks = Join-Path $env:SystemRoot "System32\schtasks.exe"

New-Item -ItemType Directory -Force -Path (Join-Path $root "runtime\logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root "runtime\secrets") | Out-Null

$prev = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& $schtasks /Delete /TN $taskName /F | Out-Null
$ErrorActionPreference = $prev

$tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""
& $schtasks /Create /TN $taskName /TR $tr /SC ONLOGON /RU Administrator /RL HIGHEST /F | Out-Null
Write-Host "Task installed: $taskName (ONLOGON, Administrator)"
& $schtasks /Query /TN $taskName /FO LIST /V | Select-String "TaskName|Status|Run As User|Task To Run"
