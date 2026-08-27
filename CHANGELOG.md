# Changelog

## 2.1.0 - 2026-08-24

- 重构为三仓职责驱动的“基金仓位决策台”；
- 使用独立 v2 SQLite、`/api/v2`、规则冻结和可回放评估；
- 接入真实公开净值、同类历史、公告候选、完整持仓与 OCR 草稿；
- 实现数据门、硬风险、质量、仓位、替代对照与用户决定冷却；
- 新增五页 React 界面、可选 DeepSeek、导出、备份和 Windows 脚本；
- 删除 Streamlit、逐笔交易、XIRR/TWR、自买入盈亏和 v1 死代码。

## 0.1.0 - 2026-07-20

- 建立完整分层架构和 SQLite 数据模型；
- 接入 AKShare 与本地 CSV Provider；
- 实现净值质量检查、收益、波动率、回撤、XIRR 和风险门控；
- 实现 Streamlit 单基金、组合、AI 证据和审计页面；
- 接入 DeepSeek v4 JSON Output、Mock 降级、缓存、预算与调用审计；
- 加入 Evidence Pack、截止日期检查和 Prompt Injection 防护；
- 增加 Windows 脚本、中文文档、示例数据、测试和 GitHub Actions。

