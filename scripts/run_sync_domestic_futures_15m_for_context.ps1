# Pull domestic server futures 15m CSVs into local data/futures/15m for context backfill.
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [string]$LogPath = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LogPath) {
    $LogPath = Join-Path $root "runtime\logs\domestic_futures_15m_sync.log"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

function Write-SyncLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    if ($env:FENGJI_SYNC_QUIET -ne "1") {
        Write-Host $line
    }
}

$mutex = [System.Threading.Mutex]::new($false, "FengJiDomesticFutures15mSync")
$mutexAcquired = $false
try {
    $mutexAcquired = $mutex.WaitOne([TimeSpan]::FromSeconds(10))
    if (-not $mutexAcquired) {
        Write-SyncLog "skipped: another sync is running"
        exit 0
    }

    $script = Join-Path $root "scripts\sync_domestic_futures_15m_for_context.py"
    if (-not (Test-Path -LiteralPath $script)) {
        throw "sync script not found: $script"
    }

    Write-SyncLog "start ssh=$SshHost remote=$RemoteRoot"
    $output = & $Python $script --ssh-host $SshHost --remote-root $RemoteRoot 2>&1 | Out-String
    $exit = $LASTEXITCODE
    foreach ($line in ($output -split "`r?`n")) {
        if ($line.Trim()) {
            Write-SyncLog $line.Trim()
        }
    }
    exit $exit
}
finally {
    if ($mutexAcquired) {
        $mutex.ReleaseMutex() | Out-Null
    }
    $mutex.Dispose()
}
