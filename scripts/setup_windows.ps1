$ErrorActionPreference = "Stop"
Write-Warning "setup_windows.ps1 是兼容入口；建议使用 scripts/install.ps1。"
& (Join-Path $PSScriptRoot "install.ps1")

