$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DatabasePath = Join-Path $ProjectRoot "data\private\fundlab_v2.sqlite3"
$BackupDirectory = Join-Path $ProjectRoot "data\backups"

if (-not (Test-Path -LiteralPath $DatabasePath)) {
    throw "尚未找到 v2 数据库。请先启动并使用一次应用。"
}

New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Destination = Join-Path $BackupDirectory "fundlab_v2-$Timestamp.sqlite3"
Copy-Item -LiteralPath $DatabasePath -Destination $Destination
Write-Host "备份已创建：$Destination" -ForegroundColor Green
