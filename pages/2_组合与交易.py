from pathlib import Path

import pandas as pd
import streamlit as st

from fundlab.config import Settings
from fundlab.services import PortfolioService
from fundlab.storage import Database

ROOT = Path(__file__).resolve().parents[1]
settings = Settings.from_env(ROOT)
database = Database(settings.database_path)
database.initialize()
service = PortfolioService(database)

st.title("组合与交易流水")
st.warning("只上传你人工整理的 CSV；不要上传支付宝密码、Cookie 或完整账户身份信息。")
uploaded = st.file_uploader("选择交易 CSV", type=["csv"])
if uploaded and st.button("导入交易流水", type="primary"):
    try:
        inserted, duplicates = service.import_csv(uploaded)
        st.success(f"新增 {inserted} 条，识别重复 {duplicates} 条")
    except Exception as exc:
        st.exception(exc)

positions = service.positions()
if positions:
    frame = pd.DataFrame(
        [{"基金": fund_id, "当前份额": shares} for fund_id, shares in positions.items()]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)
else:
    st.info("尚未导入交易流水。示例见 data/sample/transactions.csv。")
