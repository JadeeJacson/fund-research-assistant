# DeepSeek 配置

DeepSeek 默认关闭。启动应用后进入“历史与数据”，点击“配置 AI”，填写 Key、开关、模型和 Base URL。配置由本机后端原子写入项目 `.env`，保存后立即重载，不需要重启；已保存的 Key 只显示“已保存”，不会回显。默认模型为 `deepseek-v4-flash`；需要更强解释时可选择 `deepseek-v4-pro`。

也可以复制 `.env.example` 为 `.env` 后手工填写 `FUNDLAB_AI_ENABLED`、`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`，这种方式修改后需要重启后端。若同名系统环境变量存在，系统环境变量优先，页面会阻止对应字段的保存并明确提示。

“历史与数据”页会分别显示开关、Key 和模型配置状态，不再把所有配置问题统称为“未启用”。连接测试只返回安全的错误类别，不回显 Key 或上游响应正文。

连接测试只发送最小 JSON 请求。评估解释只发送公开基金身份、匿名化定量摘要和已选择 Evidence Pack；不会发送截图、OCR 原文、个人金额或完整持仓。

评估完成后，可在决策台或评估历史中点击“生成 AI 解释”。系统不会随“开始本次评估”自动调用模型；同一评估、模型与 Evidence Pack 未变化时复用本地缓存结果。没有公告证据时，模型只能解释确定性指标，并必须把文档证据缺失列入未知项。

输出必须包含 summary、supporting_points、counterpoints、unknowns；所有引用必须属于请求 Evidence Pack。模型、Prompt、Schema 或缓存键变化应升级版本并运行合约测试。

关闭、缺 Key、超时、网络失败或非法引用时，确定性评估保持完整可用。API Key 不写入数据库、前端持久化、日志或导出；配置和校验接口也不会返回 Key，校验错误会移除可能包含 Key 的输入值。
