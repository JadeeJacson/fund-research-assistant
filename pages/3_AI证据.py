from datetime import UTC, date, datetime, time
from pathlib import Path

import streamlit as st

from fundlab.ai import EvidenceAnalysisOrchestrator, build_llm_provider
from fundlab.config import Settings
from fundlab.documents import create_document_and_evidence
from fundlab.domain.enums import DocumentType, TrustLevel
from fundlab.retrieval import DatabaseRetriever
from fundlab.storage import Database

ROOT = Path(__file__).resolve().parents[1]
settings = Settings.from_env(ROOT)
database = Database(settings.database_path)
database.initialize()

st.title("AI 证据与 DeepSeek")
provider = build_llm_provider(settings)
ok, message = provider.health_check()
st.info(f"当前 Provider：{provider.name}；{message}")

fund_code = st.text_input("基金代码", max_chars=6)
share_class = st.text_input("份额类别", value="default")
subject_id = f"{fund_code}:{share_class}" if fund_code else ""

with st.form("evidence_form"):
    source_name = st.text_input("来源名称", placeholder="例如：基金管理人官方公告")
    source_url = st.text_input("来源链接（可选）")
    published_date = st.date_input("发布时间", value=date.today())
    document_type = st.selectbox(
        "文档类型", options=list(DocumentType), format_func=lambda x: x.value
    )
    trust_level = st.selectbox("来源等级", options=list(TrustLevel), format_func=lambda x: x.value)
    text = st.text_area("公告、新闻或研究材料正文", height=240)
    submitted = st.form_submit_button("保存证据")

if submitted:
    try:
        if not subject_id or len(fund_code) != 6:
            raise ValueError("请先填写六位基金代码")
        published_at = datetime.combine(published_date, time.min, tzinfo=UTC)
        document, evidence = create_document_and_evidence(
            subject_id=subject_id,
            text=text,
            source_name=source_name,
            source_url=source_url or None,
            published_at=published_at,
            document_type=document_type,
            trust_level=trust_level,
        )
        database.add_document(document)
        for item in evidence:
            database.add_evidence(item)
        st.success(f"已保存 1 份文档和 {len(evidence)} 条可引用证据")
    except Exception as exc:
        st.exception(exc)

as_of_date = st.date_input("AI 分析截止日期", value=date.today(), key="ai_as_of")
if st.button("运行结构化证据分析", type="primary"):
    try:
        evidence = DatabaseRetriever(database).retrieve_evidence(subject_id, as_of_date=as_of_date)
        orchestrator = EvidenceAnalysisOrchestrator(provider, database, settings, project_root=ROOT)
        analysis = orchestrator.analyze(
            subject_id=subject_id, as_of_date=as_of_date, evidence=evidence
        )
        st.json(analysis.model_dump(mode="json"))
    except Exception as exc:
        st.exception(exc)
