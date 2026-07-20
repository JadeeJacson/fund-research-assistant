# DeepSeek API 配置

## 当前接口选择

项目使用 DeepSeek 官方 OpenAI 兼容的 `/chat/completions` 接口：

- Base URL：`https://api.deepseek.com`
- 默认模型：`deepseek-v4-flash`
- 输出模式：`response_format={"type":"json_object"}`
- 默认关闭 Thinking，便于稳定地产生结构化事件 JSON

截至 2026-07，旧别名 `deepseek-chat` 和 `deepseek-reasoner` 即将停止服务，因此项目不再把它们设为默认值。模型可能继续升级，应优先修改 `.env`，不应在页面代码中替换模型名。

官方参考：

- [DeepSeek API Quick Start](https://api-docs.deepseek.com/)
- [JSON Output](https://api-docs.deepseek.com/guides/json_mode)
- [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)

## 获取并配置 Key

1. 登录 [DeepSeek Platform](https://platform.deepseek.com/)；
2. 创建 API Key；
3. 在项目根目录执行：

```powershell
Copy-Item .env.example .env
```

4. 修改 `.env`：

```dotenv
FUNDLAB_AI_ENABLED=true
DEEPSEEK_API_KEY=你的真实Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=false
```

5. 检查配置：

```powershell
fundlab ai-check
```

`ai-check` 只检查本地配置，不会为测试而发送付费请求。真实调用发生在“AI 证据”页面运行结构化分析时。

## 可修改设置

所有常用参数位于 `.env`：

| 变量 | 作用 |
| --- | --- |
| `DEEPSEEK_MODEL` | 模型名，升级模型时优先改这里 |
| `DEEPSEEK_THINKING` | 是否开启思考模式 |
| `DEEPSEEK_TIMEOUT_SECONDS` | 单次超时 |
| `DEEPSEEK_MAX_RETRIES` | 失败重试次数 |
| `DEEPSEEK_MAX_TOKENS` | 最大输出 Token，过低可能截断 JSON |
| `DEEPSEEK_DAILY_BUDGET_USD` | 本地日预算保护，0 表示关闭 |
| `DEEPSEEK_*_PRICE_PER_MILLION_USD` | 本地成本估算，价格变化时手动更新 |

## 代码修改位置

- API 格式或鉴权变化：`src/fundlab/ai/providers/deepseek.py`
- 模型供应商切换：在 `src/fundlab/ai/providers/` 新建适配器，再修改 `gateway.py`
- 输出字段变化：`src/fundlab/domain/models.py` 中的 `AIAnalysis`/`AIEvent`
- Prompt 修改：`prompts/event_analysis/v1_system.md`
- 安全规则：`src/fundlab/ai/safety.py`
- 固定流程：`src/fundlab/ai/orchestrator.py`

修改输出 Schema、Prompt 或模型后，必须运行 AI 测试并更新 Prompt 版本，避免旧缓存与新行为混用。

## Mock 降级

出现以下任一情况时 `build_llm_provider` 使用 Mock：

- `FUNDLAB_AI_ENABLED=false`；
- `DEEPSEEK_API_KEY` 为空；
- 测试显式要求 Mock。

Mock 不会产生真实判断，只用于验证文档、证据、Schema、缓存和页面链路。

## 安全说明

- `.env` 已被 Git 忽略；
- Key 不写入数据库和日志；
- 只发送公开证据和匿名化量化摘要；
- 不向模型发送真实账户金额、身份或支付宝流水；
- 模型无工具权限；
- API 失败不会阻止确定性报告生成。

