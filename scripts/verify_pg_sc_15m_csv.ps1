# PG/SC 15m CSV acceptance after frame_looks_acceptable deploy (run ON domestic server).
param(
    [string]$Root = "C:\Users\Administrator\quant_futures",
    [string]$BaselineScTail = "2026-07-03 06:45:00",
    [string]$BaselinePgTail = "2026-07-02 14:45:00",
    [datetime]$DeployAfter = "2026-07-03 16:19:00"
)

$ErrorActionPreference = "Stop"
Set-Location $Root

function Get-CsvTailDate([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $line = Get-Content -LiteralPath $Path -Tail 1 -Encoding UTF8
    if (-not $line) { return $null }
    $parts = $line -split ","
    return $parts[-1].Trim()
}

function Test-TailNewer([string]$Tail, [string]$Baseline) {
    if (-not $Tail -or -not $Baseline) { return $false }
    try {
        return ([datetime]$Tail) -gt ([datetime]$Baseline)
    } catch {
        return $false
    }
}

$results = @()
$allOk = $true
foreach ($sym in @("PG", "SC")) {
    $path = Join-Path $Root "data\15m\$sym.csv"
    $baseline = if ($sym -eq "PG") { $BaselinePgTail } else { $BaselineScTail }
    $item = [ordered]@{
        symbol   = $sym
        path     = $path
        exists   = $false
        mtime    = $null
        tail     = $null
        baseline = $baseline
        tail_ok  = $false
        mtime_ok = $false
        status   = "FAIL"
    }
    if (-not (Test-Path -LiteralPath $path)) {
        $item.status = "MISSING"
        $allOk = $false
        $results += [pscustomobject]$item
        continue
    }
    $fi = Get-Item -LiteralPath $path
    $tail = Get-CsvTailDate $path
    $item.exists = $true
    $item.mtime = $fi.LastWriteTime
    $item.tail = $tail
    $item.tail_ok = Test-TailNewer $tail $baseline
    $item.mtime_ok = $fi.LastWriteTime -gt $DeployAfter
    if ($item.tail_ok -or $item.mtime_ok) {
        $item.status = "PASS"
    } else {
        $item.status = "PENDING"
        $allOk = $false
    }
    $results += [pscustomobject]$item
}

Write-Host "=== PG/SC 15m CSV acceptance ===" -ForegroundColor Cyan
$results | Format-Table symbol, status, tail, baseline, mtime, tail_ok, mtime_ok -AutoSize

$dmLog = Join-Path $Root "runtime\logs\data_manager_futures.log"
if (-not (Test-Path $dmLog)) { $dmLog = Join-Path $Root "data_sync.log" }
if (Test-Path -LiteralPath $dmLog) {
    Write-Host "=== data_manager PG/SC log (last hits) ===" -ForegroundColor DarkCyan
    foreach ($sym in @("PG", "SC")) {
        $hit = Get-Content -LiteralPath $dmLog -Tail 500 -Encoding UTF8 |
            Where-Object { $_ -match "\[$sym\]|成功抓取 \[$sym\]" } |
            Select-Object -Last 2
        if ($hit) {
            Write-Host "--- $sym ---"
            $hit | ForEach-Object { Write-Host $_ }
        } else {
            Write-Host "--- $sym --- (no recent log after deploy)"
        }
    }
}

if ($allOk) {
    Write-Host "ACCEPTANCE_OK" -ForegroundColor Green
    exit 0
}

$pending = @($results | Where-Object { $_.status -eq "PENDING" })
if ($pending.Count -gt 0) {
    Write-Host "ACCEPTANCE_PENDING: wait for market window (next ~20:30) or degraded fetch round" -ForegroundColor Yellow
    exit 1
}

Write-Host "ACCEPTANCE_FAIL" -ForegroundColor Red
exit 2
