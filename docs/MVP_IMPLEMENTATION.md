# MVP 实现说明

## 1. 范围

本次 MVP 把 M1～M5 中影响主流程的能力做成一个本地可运行闭环：

```text
添加候选
  → 刷新公开数据
  → 生成两种期限报告
  → 上传并校对个人截图
  → 确认持仓与交易
  → 重新生成组合适配建议
  → 保存并检查数值触发器
  → 可选使用 Evidence Pack 和 DeepSeek 解释
```

MVP 不包含自动交易、多用户公有云、自动登录支付宝或收益保证。

## 2. 代码布局

| 路径 | 内容 |
| --- | --- |
| `backend/app/main.py` | FastAPI 路由、统一写入流程和静态前端入口 |
| `backend/app/models.py` | SQLAlchemy 数据模型 |
| `backend/app/providers.py` | AKShare 与离线演示 Provider |
| `backend/app/analytics.py` | 收益、波动和回撤 |
| `backend/app/decision.py` | 两套期限、仓位区间和操作状态 |
| `backend/app/ocr.py` | RapidOCR、页面分类和草稿解析 |
| `backend/app/ai.py` | DeepSeek 连接与 Evidence Pack 解释 |
| `backend/migrations/` | Alembic 初始迁移 |
| `frontend/src/App.tsx` | 所有 MVP 页面及真实交互 |
| `frontend/src/api.ts` | 统一 API 错误处理 |
| `backend/tests/` | API、决策、指标和 OCR 测试 |
| `frontend/e2e/` | Playwright 用户流程 |

## 3. API

核心资源：

- `/api/v1/health`
- `/api/v1/dashboard`
- `/api/v1/candidates`
- `/api/v1/reports`
- `/api/v1/holdings`
- `/api/v1/transactions`
- `/api/v1/imports`
- `/api/v1/evidence`
- `/api/v1/triggers`
- `/api/v1/settings`

接口文档由 FastAPI 在 `/api/docs` 提供。

## 4. 公开数据回退

`FUNDLAB_MARKET_PROVIDER` 支持：

- `auto`：优先 AKShare，失败时使用离线演示数据；
- `akshare`：只允许 AKShare，失败时返回明确错误；
- `demo`：固定演示数据，用于测试。

演示数据在报告和页面中明确标记，不能冒充真实行情。

## 5. 截图导入

- 图片按 SHA-256 阻止完全重复；
- Pillow 验证真实图像和像素上限；
- RapidOCR 不可用时仍创建人工校对草稿；
- OCR 结果只进入 `v1_import_items`；
- 用户确认后才写入候选、持仓或交易；
- 交易使用业务指纹去重；
- 原图默认保存在本地私有目录，可删除批次和原图；
- 删除已确认批次不会静默删除已经写入的正式记录。

## 6. 决策

报告分别计算：

- 2～3 个月；
- 约 1 年。

确定性决策至少使用：

- 基金类型；
- 当前期限历史收益；
- 最大回撤；
- 波动率；
- 当前组合权重；
- 公开数据质量；
- 主题识别和单主题上限；
- 10% 阶段性回撤参考。

DeepSeek 不参与核心数字、操作状态和目标区间的计算。

## 7. 前端按钮清单

所有可见按钮均有实际行为：

- 切换页面；
- 刷新总览；
- 添加、刷新、研究和删除候选；
- 上传截图；
- 选择批次、保存校对、确认或删除；
- 添加和删除持仓；
- 添加和删除交易；
- 添加和删除证据；
- 生成 AI 解释；
- 添加、检查和删除触发器；
- 刷新设置状态；
- 测试 AI 连接。

尚未实现的能力不展示为按钮。

## 8. 验收

本地已执行：

- 后端 pytest；
- 前端 Vitest；
- TypeScript 编译；
- Vite 生产构建；
- FastAPI 静态前端集成；
- API 关键流程；
- Alembic 升级与降级；
- Playwright 测试已纳入 CI。

真实 AKShare、RapidOCR 和 DeepSeek 属于受网络、模型和本机依赖影响的集成能力，使用健康页和设置页显示实际状态。
