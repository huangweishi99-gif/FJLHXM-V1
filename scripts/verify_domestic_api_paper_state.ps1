param(
    [string]$SshHost = "domestic-quant",
    [string]$RemoteRoot = "C:/Users/Administrator/quant_futures",
    [string]$ApiBase = "http://127.0.0.1:8000",
    [switch]$CheckApi,
    [int]$ApiRetryWaitSeconds = 5,
    [int]$ApiMaxAttempts = 3
)

$ErrorActionPreference = "Stop"

function Get-RemoteFileBytes {
    param(
        [string]$RelativePath,
        [string]$FileName
    )
    $remoteWin = Join-Path $RemoteRoot ($RelativePath -replace "/", "\")
    $raw = ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost "dir `"$remoteWin`""
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        throw "remote file missing: $remoteWin"
    }
    foreach ($line in ($raw -split "`r?`n")) {
        if ($line -notmatch [regex]::Escape($FileName)) {
            continue
        }
        if ($line -match '(\d[\d,]+)\s+' + [regex]::Escape($FileName)) {
            return [int64]($Matches[1] -replace ",", "")
        }
    }
    throw "could not parse dir output for $remoteWin"
}

$domesticBytes = Get-RemoteFileBytes -RelativePath "runtime/domestic_paper_state.json" -FileName "domestic_paper_state.json"
$overseasBytes = Get-RemoteFileBytes -RelativePath "runtime/overseas_paper_state.json" -FileName "overseas_paper_state.json"
if ($domesticBytes -le 1000 -or $overseasBytes -le 1000) {
    throw "remote paper_state files too small: domestic=$domesticBytes overseas=$overseasBytes"
}

Write-Host "DOMESTIC_API_PAPER_STATE_FILES_OK"
Write-Host ("domestic_bytes={0} overseas_bytes={1}" -f $domesticBytes, $overseasBytes)

if ($CheckApi) {
    Start-Sleep -Seconds 2
    $uri = "$($ApiBase.TrimEnd('/'))/api/v1/health"
    $raw = ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost "curl.exe -s -S -m 15 `"$uri`""
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        throw "health curl failed"
    }
    $health = $raw | ConvertFrom-Json
    if ($health.status -ne "ok") {
        throw "health not ok"
    }
    Write-Host "DOMESTIC_API_PAPER_STATE_API_OK health=$($health.status)"
}

exit 0
