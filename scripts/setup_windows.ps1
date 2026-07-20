$ErrorActionPreference = "Stop"

# 必须在项目根目录运行。脚本只创建本地环境，不写入任何 API Key。
py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "已创建 .env，请按注释填写本地设置。"
}

fundlab init-db
Write-Host "安装完成。运行 scripts/start_windows.ps1 启动。"

