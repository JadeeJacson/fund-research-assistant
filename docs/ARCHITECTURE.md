# v2.1 架构

## 运行边界

浏览器只访问本机 FastAPI。React 不直接访问 AKShare、DeepSeek、SQLite 或文件系统。后端分为 API 路由、应用服务、领域规则、Provider、证据/AI 和持久化层。

```text
React UI → /api/v2 → application services → deterministic rules
                              ├→ provider adapters / evidence
                              ├→ optional DeepSeek explanation
                              └→ SQLite + local uploads
```

## 持久化

v2 数据库为 `data/private/fundlab_v2.sqlite3`，使用 `v2_` 表和独立 Alembic 基线。核心实体包括基金/净值/同类指标、Provider 快照、组合/持仓快照/归仓、证据、候选宇宙、评估/复核项/决定、替代对照、OCR 批次和 AI 运行。

每次评估冻结规则版本和 SHA-256，记录输入指纹、数据日期、状态、进度和结果。启动时遗留的 queued/running 任务会标记 failed，用户可重试。

## API

公开契约统一位于 `/api/v2`：portfolio、snapshots、imports、funds、reviews、review decisions、alternatives、manual evidence、data health、rule config、AI test 和 full export。

普通 CI 注入 Fixture Provider；生产默认 AKShare，失败时不得自动切换 Fixture。
