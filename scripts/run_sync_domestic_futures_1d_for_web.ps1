# Pull domestic server futures 1d CSVs into local data/futures/1d (Chinese filenames for Web).
param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [string]$LogPath = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LogPath) {
    $LogPath = Join-Path $root "runtime\logs\domestic_futures_1d_sync.log"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

function Write-SyncLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$mutex = [System.Threading.Mutex]::new($false, "FengJiDomesticFutures1dSync")
$mutexAcquired = $false
try {
    $mutexAcquired = $mutex.WaitOne([TimeSpan]::FromSeconds(10))
    if (-not $mutexAcquired) {
        Write-SyncLog "skipped: another sync is running"
        exit 0
    }

    $script = Join-Path $root "scripts\sync_domestic_futures_1d_for_web.py"
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

    $metaPath = Join-Path $root "runtime\domestic_futures_1d_sync_meta.json"
    $outDir = Join-Path $root "data\futures\1d"
    $files = @()
    if (Test-Path -LiteralPath $outDir) {
        $files = Get-ChildItem -LiteralPath $outDir -Filter "*.csv" -File | Sort-Object LastWriteTime -Descending
    }
    $meta = [pscustomobject]@{
        synced_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        ok = ($exit -eq 0)
        exit_code = $exit
        ssh_host = $SshHost
        remote_root = $RemoteRoot
        local_out_dir = $outDir
        csv_count = $files.Count
        newest_csv = if ($files.Count) { $files[0].Name } else { $null }
        newest_mtime = if ($files.Count) { $files[0].LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
    }
    $meta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaPath -Encoding UTF8

    if ($exit -ne 0) {
        Write-SyncLog "failed exit=$exit"
        exit $exit
    }
    Write-SyncLog ("ok csv_count={0} newest={1}" -f $meta.csv_count, $meta.newest_csv)
    exit 0
} catch {
    Write-SyncLog ("failed: {0}" -f $_.Exception.Message)
    exit 1
} finally {
    if ($mutexAcquired) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
