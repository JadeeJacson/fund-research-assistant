$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv-mvp\Scripts\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $PythonPath)) {
    py -3.12 -m venv .venv-mvp
}

& $PythonPath -m pip install --upgrade pip
& $PythonPath -m pip install -e ".\backend[dev,market,ocr]"

Push-Location (Join-Path $ProjectRoot "frontend")
npm ci
npm run build
Pop-Location

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $ProjectRoot ".env")
}

Write-Host ""
Write-Host "MVP 安装完成。运行 .\scripts\mvp-start.ps1 启动。" -ForegroundColor Green
