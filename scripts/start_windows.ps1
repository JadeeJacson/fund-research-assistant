$ErrorActionPreference = "Stop"
Write-Warning "start_windows.ps1 是兼容入口；建议使用 scripts/start.ps1。"
& (Join-Path $PSScriptRoot "start.ps1")

