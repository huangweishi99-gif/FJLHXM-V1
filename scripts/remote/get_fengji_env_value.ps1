# Read one key from runtime/secrets/fengji_api.env (stdout = value only; for SSH piping).
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [string]$Root = "C:\Users\Administrator\quant_futures"
)

$ErrorActionPreference = "Stop"
$envPath = Join-Path $Root "runtime\secrets\fengji_api.env"
if (-not (Test-Path -LiteralPath $envPath)) { exit 1 }
foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith("#")) { continue }
    if ($t -match "^([^=]+)=(.*)$") {
        if ($matches[1].Trim() -eq $Key) {
            Write-Output $matches[2].Trim()
            exit 0
        }
    }
}
exit 1
