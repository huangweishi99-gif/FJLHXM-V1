param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [string]$LocalDomesticState = "",
    [string]$LocalOverseasState = "",
    [string]$LocalDomesticMainManifest = "",
    [string]$LocalOverseasPending = "",
    [switch]$SkipDomestic,
    [switch]$SkipOverseas,
    [switch]$SkipMainManifest,
    [switch]$SkipOverseasPending,
    [string]$LogPath = "",
    [int]$ScpRetries = 3
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LocalDomesticState) {
    $LocalDomesticState = Join-Path $root "runtime\domestic_paper_state.json"
}
if (-not $LocalOverseasState) {
    $LocalOverseasState = Join-Path $root "runtime\overseas_paper_state.json"
}
if (-not $LocalDomesticMainManifest) {
    $LocalDomesticMainManifest = Join-Path $root "runtime\domestic_futures_main_contract_sources.json"
}
if (-not $LocalOverseasPending) {
    $LocalOverseasPending = Join-Path $root "runtime\overseas_pending_orders\pending_orders.csv"
}
if (-not $LogPath) {
    $LogPath = Join-Path $root "runtime\logs\push_paper_state_to_domestic_api.log"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

function Write-PushLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    if (-not $env:FENGJI_SYNC_QUIET) { Write-Host $line }
}

function ConvertTo-ScpRemotePath {
    param([string]$WinPath)
    $normalized = ($WinPath -replace "\\", "/").TrimEnd("/")
    if ($normalized -match '^([A-Za-z]):/(.*)$') {
        return "/$($Matches[1]):/$($Matches[2])"
    }
    if ($normalized -match '^([A-Za-z]):$') {
        return "/$($Matches[1]):/"
    }
    return $normalized
}

function Copy-LocalFileWithRetry {
    param(
        [string]$LocalPath,
        [string]$RemoteRelativePath
    )
    if (-not (Test-Path -LiteralPath $LocalPath)) {
        throw "local file missing: $LocalPath"
    }
    $remoteWin = Join-Path $RemoteRoot ($RemoteRelativePath -replace "/", "\")
    $remotePosix = ConvertTo-ScpRemotePath $remoteWin
    $dest = "${SshHost}:$remotePosix"
    $lastExit = 0
    for ($attempt = 1; $attempt -le [Math]::Max(1, $ScpRetries); $attempt++) {
        scp -o BatchMode=yes -o ConnectTimeout=15 $LocalPath $dest | Out-Null
        $lastExit = $LASTEXITCODE
        if ($lastExit -eq 0) {
            return (Get-Item -LiteralPath $LocalPath).Length
        }
        if ($attempt -lt [Math]::Max(1, $ScpRetries)) {
            Start-Sleep -Seconds ([Math]::Min(10, 2 * $attempt))
        }
    }
    throw "scp failed after $ScpRetries attempt(s), exit=$lastExit dest=$dest"
}

$pushed = @()
try {
    if (-not $SkipDomestic) {
        $bytes = Copy-LocalFileWithRetry -LocalPath $LocalDomesticState -RemoteRelativePath "runtime/domestic_paper_state.json"
        $pushed += "domestic=$bytes"
    }
    if (-not $SkipOverseas) {
        $bytes = Copy-LocalFileWithRetry -LocalPath $LocalOverseasState -RemoteRelativePath "runtime/overseas_paper_state.json"
        $pushed += "overseas=$bytes"
    }
    if (-not $SkipMainManifest -and (Test-Path -LiteralPath $LocalDomesticMainManifest)) {
        $bytes = Copy-LocalFileWithRetry -LocalPath $LocalDomesticMainManifest -RemoteRelativePath "runtime/domestic_futures_main_contract_sources.json"
        $pushed += "main_manifest=$bytes"
    }
    if (-not $SkipOverseasPending -and (Test-Path -LiteralPath $LocalOverseasPending)) {
        $remotePendingDir = Join-Path $RemoteRoot "runtime\overseas_pending_orders"
        $remotePendingPosix = ConvertTo-ScpRemotePath $remotePendingDir
        ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost "powershell -NoProfile -Command ""New-Item -ItemType Directory -Force -Path '$($remotePendingDir -replace '\\','\\')' | Out-Null""" | Out-Null
        $bytes = Copy-LocalFileWithRetry -LocalPath $LocalOverseasPending -RemoteRelativePath "runtime/overseas_pending_orders/pending_orders.csv"
        $pushed += "overseas_pending=$bytes"
    }

    $meta = [pscustomobject]@{
        pushed_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        ssh_host = $SshHost
        remote_root = $RemoteRoot
        items = ($pushed -join "; ")
    }
    $metaPath = Join-Path $root "runtime\paper_state_push_meta.json"
    $meta | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $metaPath -Encoding UTF8
    Write-PushLog ("ok {0}" -f ($pushed -join " "))
    exit 0
} catch {
    Write-PushLog ("failed: {0}" -f $_.Exception.Message)
    exit 1
}
