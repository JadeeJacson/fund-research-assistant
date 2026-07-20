from pathlib import Path

import streamlit as st

from fundlab.ai import build_llm_provider
from fundlab.config import Settings
from fundlab.storage import Database

st.set_page_config(page_title="个人基金研究助手", page_icon="📊", layout="wide")

ROOT = Path(__file__).resolve().parent
settings = Settings.from_env(ROOT)
database = Database(settings.database_path)
database.initialize()
ai_provider = build_llm_provider(settings)

st.title("个人基金研究辅助系统")
st.caption("中国公募基金数据、风险指标、组合分析与 DeepSeek 证据研判")

col1, col2, col3 = st.columns(3)
col1.metric("风险参考线", f"{settings.risk_tolerance:.0%}")
col2.metric("AI Provider", ai_provider.name)
col3.metric("默认模型", getattr(ai_provider, "model", "mock"))

st.info(
    "请从左侧页面进入单基金、组合、数据质量或 AI 证据功能。"
    "未配置 DeepSeek Key 时系统自动使用 Mock 模式，确定性分析不受影响。"
)

st.markdown(
    """
### 首次使用

1. 复制 `.env.example` 为 `.env`，按注释修改本地设置。
2. 运行 `fundlab init-db` 初始化数据库。
3. 在“单基金研究”输入六位基金代码。
4. 如需 AI，先在“AI 证据”中录入带来源和日期的公告或新闻。

### 重要边界

- 系统不登录支付宝，不保存支付宝 Cookie，也不自动交易。
- 核心数字由 Python 计算；AI 只能解释已保存的证据。
- 历史表现、估值和回撤不能保证未来结果。
"""
)
