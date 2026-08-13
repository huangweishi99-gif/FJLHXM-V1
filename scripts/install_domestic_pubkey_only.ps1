# 仅重试国内公钥安装（海外已成功时用）
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_ssh_pubkeys_interactive.ps1") -Target domestic
