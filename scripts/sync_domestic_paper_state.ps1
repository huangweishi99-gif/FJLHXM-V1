param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteState = "/Users/Administrator/quant_futures/runtime/fengji_futures/state_futures_v2.json",
    [string]$RemoteMainManifest = "/Users/Administrator/quant_futures/runtime/logs/futures_main_contract_sources.json",
    [string]$LocalState = "",
    [string]$LocalMainManifest = "",
    [string]$LogPath = "",
    [int]$ScpRetries = 3
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LocalState) {
    $LocalState = Join-Path $root "runtime\domestic_paper_state.json"
}
if (-not $LocalMainManifest) {
    $LocalMainManifest = Join-Path $root "runtime\domestic_futures_main_contract_sources.json"
}
if (-not $LogPath) {
    $LogPath = Join-Path $root "runtime\logs\domestic_paper_state_sync.log"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LocalState) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LocalMainManifest) | Out-Null
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
$mutex = [System.Threading.Mutex]::new($false, "FengJiDomesticPaperStateSync")
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

    $mainManifestSynced = $false
    $mainManifestBytes = 0
    if ($RemoteMainManifest) {
        $manifestTmp = "$LocalMainManifest.tmp"
        if (Test-Path -LiteralPath $manifestTmp) {
            Remove-Item -LiteralPath $manifestTmp -Force
        }
        try {
            Copy-RemoteFileWithRetry $RemoteMainManifest $manifestTmp
            $manifestRaw = Get-Content -LiteralPath $manifestTmp -Raw -Encoding UTF8
            $manifestJson = $manifestRaw | ConvertFrom-Json
            if ($manifestJson -and $manifestJson.symbols) {
                Move-Item -LiteralPath $manifestTmp -Destination $LocalMainManifest -Force
                $mainManifestSynced = $true
                $mainManifestBytes = (Get-Item -LiteralPath $LocalMainManifest).Length
            } else {
                throw "downloaded main contract manifest is empty or invalid JSON"
            }
        } catch {
            if (Test-Path -LiteralPath $manifestTmp) {
                Remove-Item -LiteralPath $manifestTmp -Force -ErrorAction SilentlyContinue
            }
            Write-SyncLog ("warning: main contract manifest sync failed: {0}" -f $_.Exception.Message)
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
        source = "domestic_paper_state"
        ssh_host = $SshHost
        remote_state = $RemoteState
        local_state = $item.FullName
        remote_main_contract_manifest = $RemoteMainManifest
        local_main_contract_manifest = $LocalMainManifest
        main_contract_manifest_synced = $mainManifestSynced
        main_contract_manifest_bytes = $mainManifestBytes
        bytes = $item.Length
        symbols = $symbols.Count
        open_positions = $positions
    }
    $metaPath = Join-Path (Split-Path -Parent $LocalState) "domestic_paper_state_meta.json"
    $meta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaPath -Encoding UTF8

    Write-SyncLog ("ok bytes={0} symbols={1} open_positions={2} main_manifest={3}" -f $item.Length, $symbols.Count, $positions, $mainManifestSynced)
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
