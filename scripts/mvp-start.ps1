$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv-mvp\Scripts\python.exe"
$FrontendIndex = Join-Path $ProjectRoot "frontend\dist\index.html"

if (-not (Test-Path $PythonPath)) {
    throw "尚未安装 MVP。请先运行 .\scripts\mvp-install.ps1"
}

if (-not (Test-Path $FrontendIndex)) {
    Push-Location (Join-Path $ProjectRoot "frontend")
    npm run build
    Pop-Location
}

Push-Location (Join-Path $ProjectRoot "backend")
& $PythonPath -m alembic upgrade head
Write-Host "正在启动：http://127.0.0.1:8000" -ForegroundColor Cyan
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null
& $PythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
