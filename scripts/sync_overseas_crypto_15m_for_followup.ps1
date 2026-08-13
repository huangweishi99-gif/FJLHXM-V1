param(
    [string]$SshHost = "overseas-quant",
    [string]$RemoteRoot = "/home/ubuntu/quant_crypto",
    [string]$PaperState = "",
    [int]$ConnectTimeoutSec = 20
)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
if (-not $PaperState) {
    $PaperState = Join-Path $root "runtime\overseas_paper_state.json"
}

$dry = python (Join-Path $root "scripts\sync_new10_open_intraday.py") --paper-state $PaperState --dry-run 2>&1
$parsed = $dry | Select-Object -Last 1 | ConvertFrom-Json
$symbols = @($parsed.symbols)
if (-not $symbols -or $symbols.Count -eq 0) {
    Write-Host ($dry | Select-Object -Last 1)
    exit 0
}

$localDir = Join-Path $root "data\15m"
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
$ok = 0
$fail = 0
$rows = @()
foreach ($sym in $symbols) {
    $remote = "${SshHost}:${RemoteRoot}/data/15m/${sym}.csv"
    $local = Join-Path $localDir "${sym}.csv"
    scp -o BatchMode=yes -o ConnectTimeout=$ConnectTimeoutSec -o ConnectionAttempts=1 $remote $local 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $local)) {
        $ok++
        $tail = Get-Content -LiteralPath $local -Tail 1 -ErrorAction SilentlyContinue
        $rows += @{ symbol = $sym; tail = $tail }
    } else {
        $fail++
        Write-Warning "scp failed: $sym"
    }
}
Write-Host (@{
    status = if ($ok -gt 0) { "ok" } else { "partial" }
    source = "overseas"
    ok     = $ok
    fail   = $fail
    symbols = $symbols
    tails  = $rows
} | ConvertTo-Json -Compress -Depth 4)
exit 0
