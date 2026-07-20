from pathlib import Path

import pandas as pd
import streamlit as st

from fundlab.config import Settings
from fundlab.storage import Database

ROOT = Path(__file__).resolve().parents[1]
settings = Settings.from_env(ROOT)
database = Database(settings.database_path)
database.initialize()

st.title("数据质量与 AI 调用审计")

quality = database.list_quality_events()
st.subheader("数据质量事件")
if quality:
    st.dataframe(pd.DataFrame(quality), use_container_width=True, hide_index=True)
else:
    st.info("暂无数据质量事件")

runs = database.list_ai_runs()
st.subheader("AI 调用记录")
if runs:
    visible_columns = [
        "started_at",
        "subject_id",
        "provider",
        "model",
        "prompt_version",
        "latency_ms",
        "prompt_tokens",
        "completion_tokens",
        "estimated_cost_usd",
        "cached",
        "success",
        "error",
    ]
    st.dataframe(pd.DataFrame(runs)[visible_columns], use_container_width=True, hide_index=True)
else:
    st.info("暂无 AI 调用记录")
