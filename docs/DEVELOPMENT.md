# 开发说明

安装 `.\scripts\install.ps1`，开发启动 `.\scripts\dev.ps1`。后端在 8000，Vite 在 5173 并代理 `/api`。

规则只修改 `config/decision_rules.yaml`，并同步升级 version。金融公式、Provider 字段和状态变化必须补测试。前端不得加入业务计算或直接外连 Provider。

生产入口是 `app.main:app`；API 文档为 `/api/docs`。数据库变化更新 v2 Alembic 基线或新增迁移，不读取旧 v1 表。

分支使用 `codex/` 前缀，`main` 保持可启动。不要提交 `.env`、数据库、截图、备份、真实持仓或密钥。
