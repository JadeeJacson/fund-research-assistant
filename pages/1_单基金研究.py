from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fundlab.ai import EvidenceAnalysisOrchestrator, build_llm_provider
from fundlab.config import Settings
from fundlab.providers import AKShareFundProvider
from fundlab.services import FundResearchService
from fundlab.storage import Database

ROOT = Path(__file__).resolve().parents[1]
settings = Settings.from_env(ROOT)
database = Database(settings.database_path)
database.initialize()

st.title("单基金研究")
fund_code = st.text_input("基金代码", max_chars=6, placeholder="例如：000001")
include_ai = st.checkbox("同时运行 AI 证据分析", value=False)
refresh = st.checkbox("从 AKShare 刷新数据", value=True)

if st.button("开始分析", type="primary"):
    if not (fund_code.isdigit() and len(fund_code) == 6):
        st.error("请输入六位数字基金代码")
        st.stop()
    try:
        llm = build_llm_provider(settings)
        orchestrator = EvidenceAnalysisOrchestrator(llm, database, settings, project_root=ROOT)
        service = FundResearchService(
            AKShareFundProvider(), database, settings, ai_orchestrator=orchestrator
        )
        with st.spinner("正在获取并核验数据……"):
            report = service.analyze(fund_code, refresh=refresh, include_ai=include_ai)
        metrics = report.metrics
        st.subheader(f"{report.fund.fund_name}（{report.fund.fund_code}）")
        cols = st.columns(6)
        cols[0].metric("累计收益", f"{metrics.total_return:.2%}")
        cols[1].metric("年化收益", f"{metrics.annualized_return:.2%}")
        cols[2].metric("年化波动", f"{metrics.annualized_volatility:.2%}")
        cols[3].metric("最大回撤", f"{metrics.max_drawdown:.2%}")
        cols[4].metric("研究价值", report.decision.research_score)
        cols[5].metric("个人适配", report.decision.personal_fit_score)

        nav_records = database.load_nav(report.fund.fund_id)
        nav_frame = pd.DataFrame(
            {
                "日期": [item.nav_date for item in nav_records],
                "净值": [item.return_nav for item in nav_records],
            }
        )
        fig = go.Figure(go.Scatter(x=nav_frame["日期"], y=nav_frame["净值"], name="净值"))
        fig.update_layout(title="历史净值", xaxis_title="日期", yaxis_title="净值")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"状态：{report.decision.state}")
        left, right = st.columns(2)
        with left:
            st.markdown("**正面证据**")
            for item in report.decision.positive_reasons:
                st.write(f"- {item}")
        with right:
            st.markdown("**风险与未知项**")
            for item in report.decision.risk_reasons + report.decision.unknowns:
                st.write(f"- {item}")

        if report.ai_analysis:
            st.subheader("AI 证据分析")
            st.json(report.ai_analysis.model_dump(mode="json"))
        st.caption(report.disclaimer)
    except Exception as exc:
        st.exception(exc)
