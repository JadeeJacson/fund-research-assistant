# 测试与验收

后端测试覆盖规则不变量、三仓比例、完整快照门、总回报、同类连续日、硬风险优先级、最小动作、替代阈值、证据选择、决定冷却、OCR 草稿、API/导出和 AI 无 Key。

前端 Vitest 覆盖首次引导、禁用状态和五页导航；Playwright 覆盖完整持仓 → 评估 → 复核决定。Provider 合约测试使用固定数据，普通 CI 不依赖实时网络。

提交前运行：

```powershell
cd backend
..\.venv\Scripts\ruff.exe check app tests
..\.venv\Scripts\python.exe -m pytest
cd ..\frontend
npm test
npm run build
npm run e2e
```

真实 Provider smoke 是手工命令，不进入普通 CI。至少检查国内指数、主动权益、债券、QDII、黄金/商品、FOF 和货币各一只；任何失败必须显示缓存或阻断，不能出现演示回退。

```powershell
cd backend
..\.venv\Scripts\python.exe ..\scripts\live-provider-smoke.py
```

视觉验收使用 1440×900、1024×768 和窄屏截图，检查键盘操作、焦点、对比度、非颜色语义、长文本和加载稳定性。
