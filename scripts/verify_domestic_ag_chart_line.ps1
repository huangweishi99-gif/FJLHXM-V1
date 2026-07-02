# Post-deploy: 沪银 AG 峰极连线远端复验（OS state + 橡皮筋 zigzag，不写死日期）。
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Symbol = "AG"
)

$ErrorActionPreference = "Stop"
$uri = "$BaseUrl/api/v1/monitor/domestic/chart?symbol=$Symbol&strategy_id=DS03&market=FUTURES&years=2&_t=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
$bundle = Invoke-RestMethod -Uri $uri -TimeoutSec 180

if (-not $bundle.generated_at) {
    throw "missing generated_at — API may still be old build"
}
$os = $bundle.os_state
if (-not $os -or -not $os.used_os_state) {
    throw "os_state.used_os_state is false: $($os | ConvertTo-Json -Compress)"
}

$bars = @($bundle.bars)
$segs = @($bundle.hardened_segments)
if (-not $bars.Count) { throw "no bars" }
if (-not $segs.Count) { throw "no hardened_segments" }

$lastBar = $bars[-1].t
$solid = @($segs | Where-Object { ($_.style -eq "solid" -or (-not $_.style)) -and $_.kind -ne "provisional" })
$dashed = @($segs | Where-Object { $_.style -eq "dashed" -or $_.kind -eq "provisional" })

if ($dashed.Count -lt 2) {
    throw "AG expects zigzag rubber band (dashed>=2), got dashed=$($dashed.Count)"
}
if ($dashed[-1].t1 -ne $lastBar) {
    throw "trail end $($dashed[-1].t1) != last bar $lastBar"
}

$lastSolid = $solid[-1]
if ($dashed[0].t0 -ne $lastSolid.t1) {
    throw "trail must start at last solid end $($lastSolid.t1), got $($dashed[0].t0)"
}
if ([math]::Abs([double]$dashed[0].p0 - [double]$lastSolid.p1) -gt 0.01) {
    throw "trail p0 $($dashed[0].p0) != last solid p1 $($lastSolid.p1)"
}

for ($i = 0; $i -lt $dashed.Count - 1; $i++) {
    $a = $dashed[$i]
    $b = $dashed[$i + 1]
    if ($a.t1 -ne $b.t0 -or [math]::Abs([double]$a.p1 - [double]$b.p0) -gt 0.01) {
        throw "dashed chain break at leg $i : $($a.t1)@$($a.p1) -> $($b.t0)@$($b.p0)"
    }
}

# 第一段虚线应上探（最后固化为 LOW/谷 → 下一极值为 HIGH/峰）
if ($lastSolid.type -eq "LOW" -or $lastSolid.type -eq "low") {
    if ([double]$dashed[0].p1 -le [double]$dashed[0].p0) {
        throw "after LOW anchor, first trail leg should rise: $($dashed[0].p0)->$($dashed[0].p1)"
    }
}

Write-Host "AG_CHART_LINE_OK symbol=$Symbol generated_at=$($bundle.generated_at) last_bar=$lastBar solid=$($solid.Count) dashed=$($dashed.Count) anchor=$($lastSolid.t1)@$($lastSolid.p1) trail=$($dashed[0].t1)@$($dashed[0].p1)->$($dashed[-1].t1)@$($dashed[-1].p1) camp=$($os.camp)" -ForegroundColor Green
exit 0
