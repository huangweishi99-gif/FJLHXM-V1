param(
    [string]$SshHost = "domestic-quant"
)

$ErrorActionPreference = "Stop"
$remoteCmd = @(
    "powershell -NoProfile -Command",
    "'& {",
    "`$p=[bool][Environment]::GetEnvironmentVariable(''TQ_PHONE'',''Machine'') -or [bool][Environment]::GetEnvironmentVariable(''TQ_PHONE'',''User'');",
    "`$w=[bool][Environment]::GetEnvironmentVariable(''TQ_PASS'',''Machine'') -or [bool][Environment]::GetEnvironmentVariable(''TQ_PASS'',''User'');",
    "Write-Output (''TQ_ENV phone_set='' + `$p + '' pass_set='' + `$w)",
    "}'"
) -join " "

ssh -o BatchMode=yes -o ConnectTimeout=20 $SshHost $remoteCmd
