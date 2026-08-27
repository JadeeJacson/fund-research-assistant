$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    throw "尚未安装基金仓位决策台。请先运行 .\scripts\install.ps1"
}

$Backend = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot\backend'; & '$PythonPath' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

try {
    Set-Location (Join-Path $ProjectRoot "frontend")
    npm run dev
}
finally {
    Stop-Process -Id $Backend.Id -ErrorAction SilentlyContinue
}
