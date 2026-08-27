# 基金仓位决策台

一个在 Windows 本机运行的个人基金复核工具。它把完整持仓快照、公开基金数据、官方公告和透明规则组合为“无需调整信号 / 需要复核”，不会自动交易，也不会把个人金额或截图发送给大模型。

当前版本是 v2.1。旧 v1 数据库不迁移、不覆盖；v2 使用独立的 `data/private/fundlab_v2.sqlite3`。

## 已实现

- 三仓职责模型：流动防守仓 30%～50%、核心配置仓 30%～45%、卫星进攻仓 15%～30%；
- 完整持仓快照门控，计划投入金额由用户填写，可手工录入或用 RapidOCR 生成待校对草稿；
- AKShare 真实公开数据、累计净值优先、同类分位历史、公告索引、缓存和明确数据阻断；
- 数据阻断 → 硬风险 → 质量恶化 → 替代对照的确定性优先级；
- 三仓比例与目标区间独立展示，不占据首屏三件事、复核队列或 AI 解释；
- 10/20 个交易日质量连续性与用户决定冷却；
- 月度同类候选缓存、最多 50 只同类深算、最多 3 只替代对照和两次评估升级；
- 复核项“同意 / 拒绝 / 稍后”，按交易日冷却并保存备注；
- 可选 DeepSeek 结构化解释；关闭、缺 Key 或失败时不影响确定性结果；
- 五页 React 界面、完整导出、数据库备份和 Windows 启动脚本。

聚合数据或演示数据不能触发未核验的硬风险。`fixture/demo` Provider 只用于测试或显式演示，生产默认不会自动回退。

## Windows 安装与启动

需要 Python 3.12、Node.js 22 LTS 和 Git。建议把仓库放在 `D:` 或其他非系统盘；虚拟环境也会创建在仓库内。

```powershell
git clone https://github.com/JadeeJacson/fund-research-assistant.git
cd fund-research-assistant
.\scripts\install.ps1
.\scripts\start.ps1
```

浏览器访问 `http://127.0.0.1:8000`，接口文档在 `http://127.0.0.1:8000/api/docs`。

首次使用：确认预算 → 上传截图或手工录入 → 校对并确认“当前全部持仓” → 回到决策台运行评估。

## DeepSeek（可选）

启动后进入“历史与数据”→“配置 AI”，即可在本机页面中填写 Key、开关、模型和 Base URL；保存后立即生效，不需要重启。也可以继续手工复制 `.env.example` 为 `.env` 并填写：

```dotenv
FUNDLAB_AI_ENABLED=true
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=你选择的当前模型
```

已保存的 Key 不会回显，也不进入数据库、前端持久化、日志或导出。模型只接收公开基金身份、匿名定量摘要和已选择的 Evidence Pack。

## 验证与备份

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
cd ..\frontend
npm test
npm run build
npm run e2e
cd ..
.\scripts\backup.ps1
```

开发模式使用 `.\scripts\dev.ps1`。

## 边界

- 本项目是个人研究与风险复核工具，不构成收益保证或确定性投资建议；
- 不登录支付宝，不保存 Cookie、密码、交易流水或个人买入成本；
- 支付宝个人盈亏只允许作为展示事实，不参与基金质量判断；
- REITs、分级/杠杆、私募和个券只显示事实，不输出强操作结论；
- 外部字段缺失时降低结论强度或阻断，不用名称或模型猜测补齐；
- 不实现后台定时任务、云部署、认证或自动交易。

详细规范见 [文档索引](docs/INDEX.md)。
