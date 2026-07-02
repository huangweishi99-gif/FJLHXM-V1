param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteState = "/home/ubuntu/quant_crypto/runtime/fengji_paper/state.json",
    [string]$RemotePending = "/home/ubuntu/quant_crypto/runtime/fengji_pending_orders/pending_orders.csv",
    [string]$LocalState = "",
    [string]$LocalPending = "",
    [string]$LogPath = "",
    [int]$ScpRetries = 3
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LocalState) {
    $LocalState = Join-Path $root "runtime\overseas_paper_state.json"
}
if (-not $LocalPending) {
    $LocalPending = Join-Path $root "runtime\overseas_pending_orders\pending_orders.csv"
}
if (-not $LogPath) {
    $LogPath = Join-Path $root "runtime\logs\overseas_paper_state_sync.log"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LocalState) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LocalPending) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

function Write-SyncLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    if (-not $env:FENGJI_SYNC_QUIET) { Write-Host $line }
}

function Copy-RemoteFileWithRetry([string]$RemotePath, [string]$LocalPath) {
    $lastExit = 0
    for ($attempt = 1; $attempt -le [Math]::Max(1, $ScpRetries); $attempt++) {
        scp -o BatchMode=yes -o ConnectTimeout=15 "${SshHost}:$RemotePath" "$LocalPath" | Out-Null
        $lastExit = $LASTEXITCODE
        if ($lastExit -eq 0 -and (Test-Path -LiteralPath $LocalPath)) {
            return
        }
        if (Test-Path -LiteralPath $LocalPath) {
            Remove-Item -LiteralPath $LocalPath -Force -ErrorAction SilentlyContinue
        }
        if ($attempt -lt [Math]::Max(1, $ScpRetries)) {
            Start-Sleep -Seconds ([Math]::Min(10, 2 * $attempt))
        }
    }
    throw "scp failed after $ScpRetries attempt(s), exit=$lastExit remote=$RemotePath"
}

$tmp = "$LocalState.tmp"
$mutex = [System.Threading.Mutex]::new($false, "FengJiOverseasPaperStateSync")
$mutexAcquired = $false
try {
    $mutexAcquired = $mutex.WaitOne([TimeSpan]::FromSeconds(5))
    if (-not $mutexAcquired) {
        Write-SyncLog "skipped: another sync is running"
        exit 0
    }

    if (Test-Path -LiteralPath $tmp) {
        Remove-Item -LiteralPath $tmp -Force
    }

    Copy-RemoteFileWithRetry $RemoteState $tmp

    $raw = Get-Content -LiteralPath $tmp -Raw -Encoding UTF8
    $json = $raw | ConvertFrom-Json
    if ($null -eq $json) {
        throw "downloaded state is empty or invalid JSON"
    }

    Move-Item -LiteralPath $tmp -Destination $LocalState -Force

    $pendingSynced = $false
    $pendingBytes = 0
    if ($RemotePending) {
        $pendingTmp = "$LocalPending.tmp"
        if (Test-Path -LiteralPath $pendingTmp) {
            Remove-Item -LiteralPath $pendingTmp -Force
        }
        try {
            Copy-RemoteFileWithRetry $RemotePending $pendingTmp
            $pendingItem = Get-Item -LiteralPath $pendingTmp
            if ($pendingItem.Length -gt 32) {
                Move-Item -LiteralPath $pendingTmp -Destination $LocalPending -Force
                $pendingSynced = $true
                $pendingBytes = $pendingItem.Length
            } else {
                throw "downloaded pending_orders.csv is too small"
            }
        } catch {
            if (Test-Path -LiteralPath $pendingTmp) {
                Remove-Item -LiteralPath $pendingTmp -Force -ErrorAction SilentlyContinue
            }
            Write-SyncLog ("warning: pending orders sync failed: {0}" -f $_.Exception.Message)
        }
    }

    $symbols = @()
    if ($json.symbols -and $json.symbols.PSObject.Properties) {
        $symbols = @($json.symbols.PSObject.Properties.Name)
    }
    $positions = 0
    foreach ($name in $symbols) {
        $st = $json.symbols.$name
        if ($st.open_positions) {
            $positions += @($st.open_positions).Count
        }
        if ($st.open_position) {
            $positions += 1
        }
    }

    $item = Get-Item -LiteralPath $LocalState
    $meta = [pscustomobject]@{
        synced_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        source = "overseas_paper_state"
        ssh_host = $SshHost
        remote_state = $RemoteState
        local_state = $item.FullName
        remote_pending = $RemotePending
        local_pending = $LocalPending
        pending_synced = $pendingSynced
        pending_bytes = $pendingBytes
        bytes = $item.Length
        symbols = $symbols.Count
        open_positions = $positions
    }
    $metaPath = Join-Path (Split-Path -Parent $LocalState) "overseas_paper_state_meta.json"
    $meta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaPath -Encoding UTF8

    Write-SyncLog ("ok bytes={0} symbols={1} open_positions={2} pending={3}" -f $item.Length, $symbols.Count, $positions, $pendingSynced)
    exit 0
} catch {
    if (Test-Path -LiteralPath $tmp) {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    Write-SyncLog ("failed: {0}" -f $_.Exception.Message)
    exit 1
} finally {
    if ($mutexAcquired) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
