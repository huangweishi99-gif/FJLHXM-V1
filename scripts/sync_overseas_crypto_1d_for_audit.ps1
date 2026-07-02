param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteRoot = "/home/ubuntu/quant_crypto",
    [string]$LocalDir = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $LocalDir) {
    $LocalDir = Join-Path $root "data\overseas_1d"
}
New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null

$symbols = @(
    "XRPUSDT", "ATHUSDT", "WLDUSDT",
    "HYPEUSDT", "PEPEUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT",
    "RENDERUSDT", "IOUSDT", "DOGEUSDT", "LTCUSDT", "BTCUSDT", "ETHUSDT",
    "APTUSDT", "AVAXUSDT", "LINKUSDT", "TAOUSDT", "ZECUSDT", "ADAUSDT", "DASHUSDT", "SOLUSDT"
)

$ok = 0
$fail = 0
foreach ($sym in $symbols) {
    $remote = "${RemoteRoot}/data/1d/${sym}.csv"
    $local = Join-Path $LocalDir "${sym}.csv"
    scp -o BatchMode=yes -o ConnectTimeout=20 "${SshHost}:${remote}" "$local" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $local)) {
        $ok++
    } else {
        $fail++
        Write-Warning "sync failed: $sym"
    }
}
Write-Host "SYNC_OVERSEAS_1D_AUDIT ok=$ok fail=$fail dir=$LocalDir"
