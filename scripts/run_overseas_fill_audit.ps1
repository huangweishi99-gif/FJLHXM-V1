param(

    [int]$SinceHours = 72,

    [string]$Events = "",

    [string]$DataDir = "",

    [switch]$BuildSnapshot,

    [switch]$SyncEvents,

    [switch]$FailOnInvalid

)



$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Set-Location $root



if ($BuildSnapshot) {

    & (Join-Path $root "scripts\build_overseas_audit_snapshot.ps1")

}



if (-not $Events) {

    $Events = Join-Path $root "runtime\fengji_pending_orders\events_overseas_fills_${SinceHours}h.jsonl"

}

if ($SyncEvents -or -not (Test-Path -LiteralPath $Events)) {

    python (Join-Path $root "scripts\sync_overseas_fill_events.py") --since-hours $SinceHours

    if ($LASTEXITCODE -ne 0) { throw "sync_overseas_fill_events failed" }

}



$snap = Join-Path $root "runtime\audit_overseas_snapshot"

if (-not $DataDir -and (Test-Path (Join-Path $snap "1d"))) {

    $DataDir = $snap

    Write-Host "using audit snapshot: $DataDir"

}



$outDir = Join-Path $root "results\overseas_fill_audit_latest"

$ack = Join-Path $root "runtime\fill_supervision_acknowledged.json"

$cmd = @(

    "python", (Join-Path $root "scripts\audit_paper_fills.py"),

    "--profile", "overseas",

    "--since-hours", "$SinceHours",

    "--out-dir", $outDir,

    "--events", $Events,

    "--ack-file", $ack

)

if ($DataDir) { $cmd += @("--data-dir", $DataDir) }
if ($FailOnInvalid) { $cmd += "--fail-on-invalid" }

& $cmd[0] @($cmd[1..($cmd.Length - 1)])
exit $LASTEXITCODE


