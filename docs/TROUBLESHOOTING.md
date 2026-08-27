# 故障排查

- “尚未安装”：运行 `.\scripts\install.ps1`，确认 Python 3.12 和 Node.js 在 PATH；
- 公开数据刷新失败：检查网络后重试；页面不会回退演示数据，缓存过期会标 limited/blocked；
- 无法开始评估：确认最近快照勾选了“当前全部持仓”，partial 截图草稿不参与；
- OCR 失败：改用手工录入，原图不应发送给外部服务；
- AI 显示未启用：这是正常降级；需要时在本机 `.env` 填写完整配置；
- 端口占用：结束占用 8000/5173 的本地进程后重试；
- 数据库问题：先停止应用，运行 `.\scripts\backup.ps1` 保存副本，再检查 `data/private/fundlab_v2.sqlite3`。
