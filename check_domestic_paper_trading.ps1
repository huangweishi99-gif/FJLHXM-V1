# Health check: domestic server FengJi futures/A-share paper trading monitor
param(
    [string]$Server = "domestic-quant",
    [string]$User = "Administrator",
    [int]$StaleMinutes = 5
)

$ErrorActionPreference = "Stop"
$RemoteRoot = "C:\Users\Administrator\quant_futures"
$RuntimeDir = "$RemoteRoot\runtime\fengji_futures"
$LogsDir = "$RemoteRoot\runtime\logs"

$remoteScript = @'
$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\Administrator\quant_futures"
$runtime = Join-Path $root "runtime\fengji_futures"
$logs = Join-Path $root "runtime\logs"
$statusPath = Join-Path $runtime "status_futures_astock.json"
$statePath = Join-Path $runtime "state_futures_v2.json"
$eventsPath = Join-Path $runtime "events_futures_astock.jsonl"
$runLog = Join-Path $logs "futures_astock_paper_run.log"
$errLog = Join-Path $logs "futures_astock_paper_err.log"

Write-Output "===== HOST ====="
Write-Output ("Computer: {0}" -f $env:COMPUTERNAME)
Write-Output ("Now (local): {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

Write-Output ""
Write-Output "===== SSHD ====="
Get-Service sshd | Select-Object Name, Status, StartType | Format-List | Out-String | Write-Output

Write-Output "===== PYTHON (paper / fengji / 01-08) ====="
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "01-08|fengji|paper|quant_futures|国内期货" }
if (-not $procs) {
  Write-Output "NO_MATCHING_PYTHON_PROCESS"
} else {
  $procs | ForEach-Object {
    Write-Output ("PID={0} Started={1}" -f $_.ProcessId, $_.CreationDate)
    Write-Output $_.CommandLine
    Write-Output "---"
  }
}

Write-Output ""
Write-Output "===== STATUS FILE ====="
if (Test-Path $statusPath) {
  $fi = Get-Item $statusPath
  Write-Output ("path={0}" -f $statusPath)
  Write-Output ("mtime={0}" -f $fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
  Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8
} else {
  Write-Output "MISSING: $statusPath"
}

Write-Output ""
Write-Output "===== STATE FILE (head) ====="
if (Test-Path $statePath) {
  $fi = Get-Item $statePath
  Write-Output ("path={0} mtime={1}" -f $statePath, $fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
  $raw = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8
  if ($raw.Length -gt 1200) { $raw.Substring(0, 1200) + "..." } else { $raw }
} else {
  Write-Output "MISSING: $statePath"
}

Write-Output ""
Write-Output "===== EVENTS (last 5 lines) ====="
if (Test-Path $eventsPath) {
  Get-Content -LiteralPath $eventsPath -Tail 5 -Encoding UTF8
} else {
  Write-Output "MISSING: $eventsPath"
}

Write-Output ""
Write-Output "===== RUN LOG (last 15 lines) ====="
if (Test-Path $runLog) {
  Get-Content -LiteralPath $runLog -Tail 15 -Encoding UTF8
} else {
  Write-Output "MISSING: $runLog"
}

Write-Output ""
Write-Output "===== ERR LOG (last 15 lines) ====="
if (Test-Path $errLog) {
  Get-Content -LiteralPath $errLog -Tail 15 -Encoding UTF8
} else {
  Write-Output "MISSING: $errLog"
}

Write-Output ""
Write-Output "===== DATA MANAGER PYTHON ====="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "data_manager_futures" } |
  ForEach-Object { Write-Output $_.CommandLine }
'@

$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
$target = "${User}@${Server}"

Write-Host "Connecting to $target ..."
$out = ssh -o BatchMode=yes -o ConnectTimeout=20 $target "powershell -NoProfile -EncodedCommand $encoded" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "SSH failed (exit $LASTEXITCODE):" -ForegroundColor Red
    Write-Host $out
    exit $LASTEXITCODE
}

Write-Host $out

# Parse status JSON time if present
$statusBlock = ($out -split "===== STATUS FILE =====", 2)[1]
if ($statusBlock -match '\{[\s\S]*"time"\s*:\s*"([^"]+)"') {
    $statusTime = [datetime]::ParseExact($Matches[1], "yyyy-MM-dd HH:mm:ss", $null)
    $age = (Get-Date) - $statusTime
    Write-Host ""
    if ($age.TotalMinutes -le $StaleMinutes) {
        Write-Host ("VERDICT: OK — status updated {0:N1} min ago ({1})" -f $age.TotalMinutes, $Matches[1]) -ForegroundColor Green
        exit 0
    }
    Write-Host ("VERDICT: STALE — status time {0}, age {1:N1} min (threshold {2} min)" -f $Matches[1], $age.TotalMinutes, $StaleMinutes) -ForegroundColor Yellow
    exit 2
}

if ($out -match "NO_MATCHING_PYTHON_PROCESS") {
    Write-Host ""
    Write-Host "VERDICT: DOWN — no paper-trading Python process found" -ForegroundColor Red
    exit 3
}

Write-Host ""
Write-Host "VERDICT: UNKNOWN — could not parse status time; review output above" -ForegroundColor Yellow
exit 4
