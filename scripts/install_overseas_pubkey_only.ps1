# 仅重试海外公钥安装
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_ssh_pubkeys_interactive.ps1") -Target overseas
