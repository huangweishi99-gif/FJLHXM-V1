# Pull domestic server futures 5m CSVs into local data/futures/5m and ingest SQLite.
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [string]$LogPath = "",
    [string]$Python = "python",
    [switch]$SkipIngest
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LogPath) {
    $LogPath = Join-Path $root "runtime\logs\domestic_futures_5m_sync.log"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

function Write-SyncLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    if ($env:FENGJI_SYNC_QUIET -ne "1") {
        Write-Host $line
    }
}

$mutex = [System.Threading.Mutex]::new($false, "FengJiDomesticFutures5mSync")
$mutexAcquired = $false
try {
    $mutexAcquired = $mutex.WaitOne([TimeSpan]::FromSeconds(10))
    if (-not $mutexAcquired) {
        Write-SyncLog "skipped: another sync is running"
        exit 0
    }

    $script = Join-Path $root "scripts\sync_domestic_futures_5m_for_context.py"
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
    if ($exit -ne 0 -and $exit -ne 2) {
        exit $exit
    }

    if (-not $SkipIngest) {
        $db = Join-Path $root "data\market_data.sqlite"
        Write-SyncLog "ingest import-futures-local db=$db"
        $ingestOut = & $Python (Join-Path $root "src\market_data_store.py") --db $db import-futures-local --root $root 2>&1 | Out-String
        foreach ($line in ($ingestOut -split "`r?`n")) {
            if ($line.Trim()) {
                Write-SyncLog $line.Trim()
            }
        }
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    exit 0
}
finally {
    if ($mutexAcquired) {
        $mutex.ReleaseMutex() | Out-Null
    }
    $mutex.Dispose()
}
