# 个人基金研究助手

面向中国公募基金和个人实验组合的本地研究工具。系统把公开基金数据、支付宝截图中的个人事实、确定性指标、风险规则和可选 DeepSeek 解释组合成可追溯报告。

> 本项目用于个人学习、数据整理和投资研究辅助，不构成收益保证、自动投顾或交易指令。

## MVP 已实现

- React + TypeScript + Vite 桌面端；
- FastAPI + SQLAlchemy + SQLite 后端；
- Alembic 初始迁移；
- 六位基金代码候选列表；
- AKShare 公开净值刷新，失败时明确回退到离线演示数据；
- 指数基金、主动权益基金和普通债券基金的基础研究；
- 2～3 个月与约 1 年两套期限；
- 建仓候选、小幅加仓、继续持有、暂停加仓、减仓候选和退出复核；
- 约 10% 阶段性回撤参考、目标仓位区间和条件触发器；
- 主题基金识别与单主题仓位上限；
- 支付宝候选、持仓和交易截图上传；
- RapidOCR 本地识别、草稿校对、图片去重和正式确认；
- 人工持仓快照与交易流水；
- Evidence Pack 人工录入；
- DeepSeek 可选结构化解释和 Mock 降级；
- 全部页面按钮均连接真实 API 或本地动作；
- pytest、Vitest、Playwright 和 GitHub Actions；
- Windows 一键安装与启动脚本。

旧 Streamlit v0.1 仍保留，便于回归比较；新功能不再继续堆到旧页面。

## 数据如何分工

| 数据 | 来源 | 用途 |
| --- | --- | --- |
| 个人候选、持仓、交易 | 支付宝截图或人工录入 | 描述你真正关注和持有的内容 |
| 基金档案与净值 | AKShare 和后续官方 Provider | 计算确定性指标 |
| 公告、政策和新闻 | 用户录入可追溯 Evidence Pack | 补充事件影响和反方证据 |
| AI 解释 | DeepSeek 读取结构化报告与 Evidence Pack | 解释，不改变数字和操作状态 |

支付宝详情页截图不能代替基金公开研究。DeepSeek 不直接接收原始图片。

## Windows 快速开始

需要：

- Windows 10/11；
- Python 3.12；
- Node.js 22 LTS；
- Git。

首次安装：

```powershell
git clone https://github.com/JadeeJacson/fund-research-assistant.git
cd fund-research-assistant
.\scripts\mvp-install.ps1
```

安装脚本会：

1. 创建 `.venv-mvp`；
2. 安装 FastAPI、AKShare、RapidOCR 等依赖；
3. 安装前端依赖并生成生产构建；
4. 在不存在时复制 `.env.example` 为 `.env`。

启动：

```powershell
.\scripts\mvp-start.ps1
```

浏览器会打开：

```text
http://127.0.0.1:8000
```

开发模式：

```powershell
.\scripts\mvp-dev.ps1
```

前端地址为 `http://127.0.0.1:5173`，API 为 `http://127.0.0.1:8000/api/v1`，接口文档为 `http://127.0.0.1:8000/api/docs`。

## 首次使用顺序

1. 在“候选研究”添加六位基金代码；
2. 点击“刷新公开数据”；
3. 分别运行“研究 2～3 个月”和“研究约 1 年”；
4. 如有支付宝截图，在“截图导入”上传并逐字段校对；
5. 确认导入后查看持仓和交易；
6. 为候选报告录入公告或可靠新闻证据；
7. 可选启用 DeepSeek，再生成结构化解释；
8. 在“条件触发”保存阈值并主动检查。

若页面标记“离线演示数据”，只能用于验证流程，不能作为实际操作依据。

## DeepSeek

编辑本机 `.env`：

```dotenv
FUNDLAB_AI_ENABLED=true
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=按当前官方文档填写
```

模型名不在代码中写死。设置页的“测试 AI 连接”只发送最小匿名请求，不包含截图、持仓或交易。没有密钥时确定性分析仍可运行。

## 测试

后端：

```powershell
cd backend
..\.venv-mvp\Scripts\python.exe -m pytest
```

前端：

```powershell
cd frontend
npm test
npm run build
npm run e2e
```

## MVP 已知边界

- AKShare 是便利入口，不是官方法定披露来源；
- 当前事件证据需要人工提供 URL 和正文，尚未自动抓取官方公告；
- OCR 可以识别截图中的可见内容，但不能恢复 UI 已截断文本；
- 交易列表截图通常缺少确认净值、份额和费用，精确收益计算前必须补录；
- 行业/主题仓位由可审计规则约束，不由 AI 自由分配；
- 10% 是阶段性风险参考，不是止损保证；
- 本地触发器需要用户主动检查；
- 当前是单用户本地应用，不能直接暴露到公网。

后续事项保留在 [实施路线](docs/ROADMAP.md)，MVP 的实际实现对应关系见 [MVP 实现说明](docs/MVP_IMPLEMENTATION.md)。

## 文档

- [文档索引](docs/INDEX.md)
- [产品需求](docs/PRODUCT_REQUIREMENTS.md)
- [项目状态](docs/PROJECT_STATUS.md)
- [目标架构](docs/ARCHITECTURE.md)
- [数据来源](docs/DATA_SOURCES.md)
- [截图导入](docs/DATA_IMPORT.md)
- [决策引擎](docs/DECISION_ENGINE.md)
- [前端交互](docs/FRONTEND_CONTRACT.md)
- [测试与验收](docs/TESTING_ACCEPTANCE.md)
- [安全与隐私](docs/SECURITY.md)

## 重要边界

- 不登录支付宝；
- 不保存支付宝 Cookie、密码或账户凭据；
- 不自动申购、赎回、转换或调仓；
- 不让大模型生成核心金融数字；
- 不把单位净值低简单解释为“便宜”；
- 不在资料不足时伪造强结论。
