param(
    [string]$Server = "overseas-quant",
    [string]$User = "ubuntu",
    [int]$Port = 22,
    [string]$RemoteDir = "/home/ubuntu/quant_crypto"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SrcDir = Join-Path $ProjectRoot "src"
$ZipPath = Join-Path $ProjectRoot "src.zip"
$Remote = "$User@$Server"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$RemoteScriptName = ".deploy_src_$Stamp.sh"
$RemoteScriptPath = "$RemoteDir/$RemoteScriptName"
$LocalRemoteScript = Join-Path $ProjectRoot $RemoteScriptName

if (-not (Test-Path $SrcDir)) {
    throw "Local src folder not found: $SrcDir"
}

if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Write-Host "Compressing local src folder..."
Compress-Archive -Path $SrcDir -DestinationPath $ZipPath -Force

$remoteScript = @'
set -e
cd "REMOTE_DIR_PLACEHOLDER"
backup="src_backup_STAMP_PLACEHOLDER"
if [ -d src ]; then
  mv src "$backup"
  echo "Backup created: $backup"
fi
if ! unzip -q -o src.zip; then
  echo "Unzip failed. Restoring previous src..."
  rm -rf src
  if [ -d "$backup" ]; then
    mv "$backup" src
  fi
  exit 1
fi
find src -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
rm -f "SCRIPT_NAME_PLACEHOLDER"
echo "Deploy completed."
ls -la src | head -30
'@ -replace 'REMOTE_DIR_PLACEHOLDER', $RemoteDir -replace 'STAMP_PLACEHOLDER', $Stamp -replace 'SCRIPT_NAME_PLACEHOLDER', $RemoteScriptName

Set-Content -LiteralPath $LocalRemoteScript -Value $remoteScript -Encoding ascii

try {
    Write-Host "Uploading src.zip to ${Remote}:${RemoteDir}/src.zip ..."
    scp -P $Port $ZipPath "${Remote}:${RemoteDir}/src.zip"

    Write-Host "Uploading remote deploy script..."
    scp -P $Port $LocalRemoteScript "${Remote}:${RemoteScriptPath}"

    Write-Host "Running remote deploy script..."
    ssh -p $Port $Remote "bash '$RemoteScriptPath'"

    Write-Host ""
    Write-Host "Done. If the paper monitor is running, restart it manually to load the new code."
}
finally {
    if (Test-Path $LocalRemoteScript) {
        Remove-Item -LiteralPath $LocalRemoteScript -Force
    }
}
