param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteRoot = "/home/ubuntu/quant_crypto",
    [string]$OutDir = "",
    [string[]]$Symbols = @(),
    [string[]]$Timeframes = @("1d", "1h", "15m")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutDir) {
    $OutDir = Join-Path $root "runtime\audit_overseas_snapshot"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (-not $Symbols -or $Symbols.Count -eq 0) {
    $Symbols = @(
        "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "WLDUSDT",
        "APTUSDT", "AVAXUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "LINKUSDT", "TAOUSDT", "ZECUSDT",
        "ADAUSDT", "DASHUSDT", "SOLUSDT", "RENDERUSDT", "BNBUSDT", "LTCUSDT", "TRUMPUSDT"
    )
}

$ok = 0
$fail = 0
foreach ($tf in $Timeframes) {
    $localTf = Join-Path $OutDir $tf
    New-Item -ItemType Directory -Force -Path $localTf | Out-Null
    foreach ($sym in $Symbols) {
        $remote = "${RemoteRoot}/data/$tf/${sym}.csv"
        $local = Join-Path $localTf "${sym}.csv"
        scp -o BatchMode=yes -o ConnectTimeout=20 "${SshHost}:${remote}" "$local" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $local)) {
            $ok++
        } else {
            $fail++
        }
    }
}
Write-Host "AUDIT_SNAPSHOT ok=$ok fail=$fail dir=$OutDir"
if ($fail -gt 0) { exit 1 }
exit 0
