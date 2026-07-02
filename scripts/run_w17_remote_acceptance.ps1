# W17-prod 远端验收一键脚本（本机执行）
param(
    [switch]$Local,
    [switch]$PreflightOnly,
    [string]$BaseUrl = "",
    [string]$SshTunnel = "domestic-quant",
    [int]$LocalPort = 8040,
    [string]$AdminToken = "",
    [switch]$FetchRemoteAdminToken,
    [switch]$SkipWeb,
    [switch]$AutoServer
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$acceptance = Join-Path $PSScriptRoot "w17_remote_acceptance.py"
if (-not (Test-Path -LiteralPath $acceptance)) {
    throw "Missing $acceptance"
}

$localEnv = Join-Path $Root "runtime\secrets\fengji_local.env"
if (Test-Path -LiteralPath $localEnv) {
    Get-Content -LiteralPath $localEnv -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        if ($line -match "^([^=]+)=(.*)$") {
            Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim()
        }
    }
}

$pyArgs = @("$acceptance")

if ($PreflightOnly) {
    $pyArgs += @("--preflight-only", "--preflight-ssh", $SshTunnel)
} elseif ($Local -and -not $BaseUrl) {
    if ($AutoServer) {
        $pyArgs += @("--auto-server", "--port", "8042")
    } else {
        $BaseUrl = "http://127.0.0.1:8000"
        Write-Host "[local] 假定 API 已运行: $BaseUrl （或加 -AutoServer）" -ForegroundColor Cyan
        $pyArgs += @("--base-url", $BaseUrl)
    }
} elseif ($SshTunnel -and -not $BaseUrl) {
    Write-Host "[remote] SSH 隧道 $SshTunnel -> 127.0.0.1:$LocalPort" -ForegroundColor Cyan
    $pyArgs += @("--ssh-tunnel", $SshTunnel, "--local-port", $LocalPort)
} elseif ($BaseUrl) {
    $pyArgs += @("--base-url", $BaseUrl.TrimEnd("/"))
} else {
    $pyArgs += @("--auto-server", "--port", "8042")
}

if ($AdminToken) {
    $pyArgs += @("--admin-token", $AdminToken)
} elseif ($FetchRemoteAdminToken -and $SshTunnel -and -not $Local) {
    $remoteScript = "C:\Users\Administrator\quant_futures\scripts\remote\get_fengji_env_value.ps1"
    $remoteToken = ssh -o BatchMode=yes $SshTunnel "powershell -NoProfile -ExecutionPolicy Bypass -File `"$remoteScript`" -Key FENGJI_ADMIN_TOKEN" 2>$null
    if ($remoteToken) {
        $pyArgs += @("--admin-token", $remoteToken.Trim())
        Write-Host "[remote] loaded FENGJI_ADMIN_TOKEN from server env (not printed)" -ForegroundColor DarkGray
    }
} elseif ($env:FENGJI_ADMIN_TOKEN) {
    $pyArgs += @("--admin-token", $env:FENGJI_ADMIN_TOKEN)
}

if ($SkipWeb) {
    $pyArgs += "--no-web"
}

$displayArgs = ($pyArgs | ForEach-Object {
    if ($_ -eq "--admin-token") { return $_ }
    if ($pyArgs[[array]::IndexOf($pyArgs, $_) - 1] -eq "--admin-token") { return "***" }
    $_
}) -join " "
Write-Host "python $displayArgs" -ForegroundColor DarkGray
& python @pyArgs
exit $LASTEXITCODE
