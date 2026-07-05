# Kill duplicate data_manager only; start one when heartbeat dead. Does NOT touch paper/radar/pending.
$ErrorActionPreference = "Stop"
$root = "C:\Users\Administrator\quant_futures"
$py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$heartbeatFile = Join-Path $root "runtime\logs\data_manager_heartbeat.txt"
$heartbeatMaxAgeSec = 420
$dataStaleLimitSec = 1500
Set-Location $root

function Get-DmProcs {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and ($_.CommandLine -match "data_manager_futures\.py")
    })
}

function Get-DmPythonProcs {
    @(Get-DmProcs | Where-Object { $_.Name -match "python" })
}

function Get-DmHeartbeatNote {
    if (-not (Test-Path $heartbeatFile)) { return "" }
    $line = Get-Content $heartbeatFile -TotalCount 1 -ErrorAction SilentlyContinue
    if ($line -match "pid=\d+\s+(.+)$") { return $Matches[1].Trim() }
    return ""
}

function Get-Latest15mAge {
    $csv = Get-ChildItem (Join-Path $root "data\15m") -Filter "*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $csv) { return $null }
    return ((Get-Date) - $csv.LastWriteTime).TotalSeconds
}

function Get-DmPythonCount {
    return @(Get-DmPythonProcs).Count
}

function Ensure-SingleDataManager {
    $pyCount = Get-DmPythonCount
    if ($pyCount -le 1) { return $pyCount }
    $pyProcs = @(Get-DmPythonProcs)
    Write-Host "dedupe after start: stopping $($pyProcs.Count) python processes..."
    foreach ($p in $pyProcs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    foreach ($p in (Get-DmProcs | Where-Object { $_.Name -notmatch "python" })) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Seconds 2
    return Get-DmPythonCount
}

function Test-DmAlive {
    if ((Get-DmPythonCount) -eq 0) { return $false }
    $dataAge = Get-Latest15mAge
    $note = Get-DmHeartbeatNote
    if ($null -ne $dataAge -and $dataAge -gt $dataStaleLimitSec -and $note -match "connect_retry|connect") {
        return $false
    }
    if (Test-Path $heartbeatFile) {
        $age = ((Get-Date) - (Get-Item $heartbeatFile).LastWriteTime).TotalSeconds
        if ($age -lt $heartbeatMaxAgeSec) { return $true }
    }
    if ($null -ne $dataAge -and $dataAge -lt $dataStaleLimitSec) { return $true }
    return $false
}

function Test-DmBinaryStale {
    $pyProcs = @(Get-DmPythonProcs)
    if ($pyProcs.Count -eq 0) { return $false }
    $codePath = Join-Path $root "data_manager_futures.py"
    if (-not (Test-Path -LiteralPath $codePath)) { return $false }
    $codeMtime = (Get-Item -LiteralPath $codePath).LastWriteTime
    foreach ($p in $pyProcs) {
        if ($codeMtime -gt $p.CreationDate) { return $true }
    }
    return $false
}

function Test-DmNeedsCatchup {
    try {
        & $py -c "import data_manager_futures as dm; raise SystemExit(0 if dm.needs_stale_catchup() else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$procs = @(Get-DmProcs)
$pyProcs = @(Get-DmPythonProcs)
Write-Host "data_manager procs=$($procs.Count) python=$($pyProcs.Count)"
if (Test-Path $heartbeatFile) {
    Write-Host "heartbeat: $(Get-Content $heartbeatFile -TotalCount 1)"
}

if ($pyProcs.Count -gt 1) {
    Write-Host "dedupe: stopping $($pyProcs.Count) python processes..."
    foreach ($p in $pyProcs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Host "stopped PID=$($p.ProcessId)" } catch {}
    }
    foreach ($p in (Get-DmProcs | Where-Object { $_.Name -notmatch "python" })) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Seconds 3
}

$procs = @(Get-DmProcs)
$pyProcs = @(Get-DmPythonProcs)
if ($pyProcs.Count -gt 1) {
    Write-Host "WARN still $($pyProcs.Count) python after dedupe"
    exit 1
}

if ($pyProcs.Count -eq 1 -and (Test-DmBinaryStale)) {
    Write-Host "code newer than PID=$($pyProcs[0].ProcessId) — restarting for fresh module..."
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Seconds 3
    $procs = @(Get-DmProcs)
    $pyProcs = @(Get-DmPythonProcs)
}

if ($pyProcs.Count -eq 1 -and (Test-DmNeedsCatchup)) {
    Write-Host "1d bar stale — restarting PID=$($pyProcs[0].ProcessId) for CATCHUP..."
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    Start-Sleep -Seconds 3
    $procs = @(Get-DmProcs)
    $pyProcs = @(Get-DmPythonProcs)
}

if ($pyProcs.Count -eq 1) {
    Write-Host "ok PID=$($pyProcs[0].ProcessId)"
    exit 0
}

if (Test-DmAlive) {
    Write-Host "ok (heartbeat alive, no strict python proc — will start)"
}

$lockDir = Join-Path $root "runtime\watchdog"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lock = Join-Path $lockDir "data_manager_start.lock"
if ((Test-Path $lock) -and (((Get-Date) - (Get-Item $lock).LastWriteTime).TotalSeconds -lt 30)) {
    Write-Host "launch lock active, skip"
    exit 0
}
Set-Content -Path $lock -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
try {
    $cmd = "cmd.exe /d /c cd /d `"$root`" && set `"PYTHONPATH=src;packages/fengji_core`"&& set FENGJI_MARKET=futures&& set PYTHONIOENCODING=utf-8&& set PYTHONUTF8=1&& `"$py`" -u data_manager_futures.py >> runtime\logs\data_manager_futures.log 2>> runtime\logs\data_manager_futures_err.log"
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root } | Out-Null
    Start-Sleep -Seconds 8
    if (Test-DmAlive) {
        if ((Get-DmPythonCount) -gt 1) { Ensure-SingleDataManager | Out-Null }
        Write-Host "started ok"
        exit 0
    }
    Start-Sleep -Seconds 20
    if (Test-DmAlive) {
        if ((Get-DmPythonCount) -gt 1) { Ensure-SingleDataManager | Out-Null }
        Write-Host "started ok (slow tqsdk connect)"
        exit 0
    }
    Write-Host "start failed"; exit 1
} finally {
    Remove-Item $lock -ErrorAction SilentlyContinue
}
