$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $PythonPath)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        & $PyLauncher.Source -3.12 -m venv .venv
    }
    elseif ($PythonCommand) {
        & $PythonCommand.Source -m venv .venv
    }
    else {
        throw "未找到 Python 3.12。请安装 Python 3.12，并在安装器中勾选加入 PATH。"
    }
}

$env:PIP_NO_CACHE_DIR = "1"
& $PythonPath -m ensurepip --upgrade --default-pip
& $PythonPath -m pip install --disable-pip-version-check "setuptools==80.9.0" "wheel==0.45.1"
& $PythonPath -m pip install --no-build-isolation -e ".\backend[dev,market,ocr]"

Push-Location (Join-Path $ProjectRoot "frontend")
npm ci
npm run e2e:install
npm run build
Pop-Location

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $ProjectRoot ".env")
}

Write-Host ""
Write-Host "基金仓位决策台 v2.1 安装完成。运行 .\scripts\start.ps1 启动。" -ForegroundColor Green
