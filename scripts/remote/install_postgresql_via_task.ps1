# Run EDB PostgreSQL installer via one-shot Scheduled Task (Highest) — avoids SSH session bat write failures.
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [Parameter(Mandatory = $true)]
    [string]$SuperPassword,
    [int]$PgPort = 5432,
    [string]$Root = "C:\Users\Administrator\quant_futures",
    [string]$TaskName = "FengJiPgInstallOnce"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $InstallerPath)) { throw "Missing installer: $InstallerPath" }

$workTemp = Join-Path $Root "runtime\temp"
New-Item -ItemType Directory -Force -Path $workTemp | Out-Null
$logDir = Join-Path $Root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$installLog = Join-Path $logDir "pg_install_task_$stamp.log"
$wrapper = Join-Path $workTemp "fengji_pg_install.cmd"
$doneFlag = Join-Path $workTemp "fengji_pg_install.done"
$exitFile = Join-Path $workTemp "fengji_pg_install.exitcode"

Remove-Item -LiteralPath $doneFlag, $exitFile -Force -ErrorAction SilentlyContinue

$wrapperLines = @(
    "@echo off",
    "setlocal",
    "set TEMP=$workTemp",
    "set TMP=$workTemp",
    "set ComSpec=%SystemRoot%\System32\cmd.exe",
    "set COMSPEC=%SystemRoot%\System32\cmd.exe",
    "cd /d `"$workTemp`"",
    "echo [%DATE% %TIME%] starting installer >> `"$installLog`"",
    "`"$InstallerPath`" --mode unattended --unattendedmodeui none --superpassword `"$SuperPassword`" --servicename postgresql-x64-16 --servicepassword `"$SuperPassword`" --serverport $PgPort >> `"$installLog`" 2>&1",
    "set EC=%ERRORLEVEL%",
    "echo %EC% > `"$exitFile`"",
    "echo done > `"$doneFlag`"",
    "exit /b %EC%"
)
Set-Content -LiteralPath $wrapper -Value ($wrapperLines -join "`r`n") -Encoding ASCII

schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
$create = schtasks /Create /TN $TaskName /TR "cmd.exe /c `"$wrapper`"" /SC ONCE /ST 00:00 /RL HIGHEST /F
if ($LASTEXITCODE -ne 0) { throw "schtasks create failed: $create" }
schtasks /Run /TN $TaskName | Out-Null
Write-Host "Scheduled task $TaskName started; log=$installLog"

$deadline = (Get-Date).AddMinutes(25)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    if (Test-Path -LiteralPath $doneFlag) { break }
    $state = (schtasks /Query /TN $TaskName /FO LIST /V 2>$null | Select-String "Status:" | Select-Object -First 1)
    Write-Host "  waiting... $state"
}
if (-not (Test-Path -LiteralPath $doneFlag)) {
    Write-Host "Install log tail:" -ForegroundColor Yellow
    if (Test-Path -LiteralPath $installLog) { Get-Content -LiteralPath $installLog -Tail 30 }
    throw "Installer task timeout after 25 min"
}
$exitCode = 1
if (Test-Path -LiteralPath $exitFile) { $exitCode = [int](Get-Content -LiteralPath $exitFile -Raw).Trim() }
Write-Host "Installer exit code: $exitCode"
if ($exitCode -ne 0) {
    if (Test-Path -LiteralPath $installLog) { Get-Content -LiteralPath $installLog -Tail 30 }
    exit $exitCode
}
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
Write-Host "PostgreSQL installer task OK"
