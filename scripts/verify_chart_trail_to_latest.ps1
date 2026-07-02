# Verify chart hardened line reaches latest bar date.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string[]]$Symbols = @("RB", "AG", "LC")
)

$ErrorActionPreference = "Stop"
$symbolList = @()
foreach ($s in $Symbols) {
    if ($s -match ',') {
        $symbolList += ($s -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    } else {
        $symbolList += $s
    }
}
$failed = 0
foreach ($symbol in $symbolList) {
    $uri = "$BaseUrl/api/v1/monitor/domestic/chart?symbol=$symbol&strategy_id=DS03&market=FUTURES&years=2"
    $bundle = Invoke-RestMethod -Uri $uri -TimeoutSec 180
    $bars = @($bundle.bars)
    $segs = @($bundle.hardened_segments)
    if (-not $bars.Count) {
        Write-Host "FAIL $symbol no bars" -ForegroundColor Red
        $failed++
        continue
    }
    if (-not $segs.Count) {
        Write-Host "FAIL $symbol no segments" -ForegroundColor Red
        $failed++
        continue
    }
    $lastBar = $bars[-1].t
    $lastSeg = $segs[-1]
    if ($lastSeg.t1 -ne $lastBar) {
        Write-Host "FAIL $symbol last_seg=$($lastSeg.t1) last_bar=$lastBar" -ForegroundColor Red
        $failed++
        continue
    }
    $dashed = @($segs | Where-Object { $_.style -eq "dashed" -or $_.kind -eq "provisional" })
    if (-not $dashed.Count) {
        Write-Host "FAIL $symbol missing provisional dashed segments" -ForegroundColor Red
        $failed++
        continue
    }
    if ($dashed[-1].t1 -ne $lastBar) {
        Write-Host "FAIL $symbol trail_end=$($dashed[-1].t1) last_bar=$lastBar" -ForegroundColor Red
        $failed++
        continue
    }
    Write-Host "OK $symbol last_bar=$lastBar solid=$(@($segs | Where-Object { $_.style -eq 'solid' -or (-not $_.style -and $_.kind -ne 'provisional') }).Count) dashed=$($dashed.Count)" -ForegroundColor Green
}
if ($failed -gt 0) { exit 1 }
exit 0
