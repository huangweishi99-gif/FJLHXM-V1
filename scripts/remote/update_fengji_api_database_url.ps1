# Update DATABASE_URL in runtime/secrets/fengji_api.env without rotating JWT/ADMIN tokens.
param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$secretDir = Join-Path $Root "runtime\secrets"
$envPath = Join-Path $secretDir "fengji_api.env"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing $envPath — run create_fengji_api_env.ps1 first"
}

$backup = Join-Path $secretDir ("fengji_api.env.bak_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
Copy-Item -LiteralPath $envPath -Destination $backup -Force
Write-Host "Backed up env to $(Split-Path $backup -Leaf)"

$lines = Get-Content -LiteralPath $envPath -Encoding UTF8
$found = $false
$out = foreach ($line in $lines) {
    if ($line -match '^\s*DATABASE_URL=') {
        $found = $true
        "DATABASE_URL=$DatabaseUrl"
    } else {
        $line
    }
}
if (-not $found) {
    $out = @($out) + "DATABASE_URL=$DatabaseUrl"
}
Set-Content -LiteralPath $envPath -Value ($out -join "`n") -Encoding UTF8
Write-Host "Updated DATABASE_URL in fengji_api.env (value not printed)."
