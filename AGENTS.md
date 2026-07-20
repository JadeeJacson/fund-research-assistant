# 项目协作约束

- 核心金融指标必须由确定性代码计算，不允许由大模型生成。
- 任何 AI 结论必须引用已有 `evidence_id`，并通过 Pydantic 校验。
- 不得提交 `.env`、数据库、真实持仓、支付宝 Cookie 或 API Key。
- 上游 Provider 变化时只修改 `src/fundlab/providers/`，不要让页面直接调用 AKShare。
- DeepSeek 或其他模型变化时只修改 `src/fundlab/ai/providers/` 和配置。
- 新公式必须包含单元测试；Prompt 或模型变化必须运行 AI Golden Set。
- 不实现自动交易，不把研究状态描述成确定性投资建议。

