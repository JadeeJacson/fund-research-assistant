$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    throw "未找到 .venv，请先运行 scripts/setup_windows.ps1"
}

& .\.venv\Scripts\Activate.ps1
streamlit run app.py

