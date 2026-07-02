# Fix TEMP/TMP for PostgreSQL EDB installer on domestic server (run via SSH as Administrator).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$workTemp = Join-Path $Root "runtime\temp"
New-Item -ItemType Directory -Force -Path $workTemp | Out-Null

# Project-local temp (always writable under quant_futures)
icacls $workTemp /grant "Administrators:(OI)(CI)F" /T | Out-Null
icacls $workTemp /grant "${env:USERNAME}:(OI)(CI)F" /T | Out-Null

# Repair default user Temp if missing or broken
$userTemp = Join-Path $env:USERPROFILE "AppData\Local\Temp"
if (-not (Test-Path -LiteralPath $userTemp)) {
    New-Item -ItemType Directory -Force -Path $userTemp | Out-Null
}
icacls $userTemp /grant "Administrators:(OI)(CI)F" /T 2>$null | Out-Null
icacls $userTemp /grant "${env:USERNAME}:(OI)(CI)F" /T 2>$null | Out-Null

# Session + persistent user env for installer subprocesses
[Environment]::SetEnvironmentVariable("TEMP", $workTemp, "User")
[Environment]::SetEnvironmentVariable("TMP", $workTemp, "User")
$env:TEMP = $workTemp
$env:TMP = $workTemp

# Smoke write
$probe = Join-Path $workTemp ("probe_" + [Guid]::NewGuid().ToString("n") + ".txt")
Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8
Remove-Item -LiteralPath $probe -Force

Write-Host "TEMP fixed -> $workTemp"
Write-Host "userTemp exists -> $(Test-Path -LiteralPath $userTemp)"
