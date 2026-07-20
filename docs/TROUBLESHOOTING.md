# 故障排查

## AKShare 获取失败

1. 升级 AKShare：`pip install --upgrade akshare`；
2. 运行 `fundlab analyze <代码>` 查看错误；
3. 查看“数据质量”页面；
4. 如果本地已有缓存，使用 `--no-refresh`；
5. 上游字段变化时只修改 `akshare_provider.py`；
6. 临时使用 `ManualCsvProvider`。

## DeepSeek 返回空内容或 JSON 不完整

- 增大 `DEEPSEEK_MAX_TOKENS`；
- 保持 Prompt 中明确要求 JSON；
- 检查模型名是否仍可用；
- 查看“数据质量”页面中的 AI 调用错误；
- 删除 `data/cache/ai/` 中对应缓存后重试；
- 不要无限增加重试次数，以免产生意外费用。

## AI 页面总是 Mock

检查：

```dotenv
FUNDLAB_AI_ENABLED=true
DEEPSEEK_API_KEY=非空
```

修改 `.env` 后重启 Streamlit。

## 数据库锁定

本项目为单用户本地应用。关闭重复运行的 Streamlit 或脚本后重试。若需要多进程写入或云端多用户，应迁移到 PostgreSQL，而不是继续扩大 SQLite 的使用范围。

## Streamlit 找不到 fundlab

确认已在虚拟环境中执行：

```powershell
pip install -e ".[dev]"
```

