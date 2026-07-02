param(
    [switch]$SkipDomesticSync,
    [switch]$SkipOverseasSync,
    [switch]$SkipPush,
    [switch]$Verify,
    [switch]$VerifyApi
)

$ErrorActionPreference = "Stop"
$env:FENGJI_SYNC_QUIET = "1"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$domesticSync = Join-Path $root "scripts\sync_domestic_paper_state.ps1"
$overseasSync = Join-Path $root "scripts\sync_overseas_paper_state.ps1"
$pushScript = Join-Path $root "scripts\push_paper_state_to_domestic_api.ps1"
$verifyScript = Join-Path $root "scripts\verify_domestic_api_paper_state.ps1"

function Invoke-StepScript {
    param(
        [string]$Path,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "missing script: $Path"
    }
    # 同进程调用，避免计划任务里再弹出 3 个子 PowerShell 窗口
    & $Path
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipDomesticSync) {
    Invoke-StepScript -Path $domesticSync -Label "domestic paper_state sync"
}

if (-not $SkipOverseasSync) {
    Invoke-StepScript -Path $overseasSync -Label "overseas paper_state sync"
}

if (-not $SkipPush) {
    Invoke-StepScript -Path $pushScript -Label "push paper_state to domestic API"
}

if ($Verify) {
    $verifyArgs = @{}
    if ($VerifyApi) { $verifyArgs["CheckApi"] = $true }
    & $verifyScript @verifyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "domestic API paper_state verify failed with exit code $LASTEXITCODE"
    }
}

Write-Host "SYNC_AND_PUSH_PAPER_STATE_OK"
exit 0
