# 开发与维护

## 环境

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 命令

```powershell
fundlab init-db
fundlab ai-check
fundlab analyze 000001
fundlab analyze 000001 --ai
streamlit run app.py
ruff check .
pytest
```

无 pytest 时，当前测试同样兼容标准库：

```powershell
python -m unittest discover -s tests -v
```

## 常见修改位置

| 需求 | 文件 |
| --- | --- |
| 修改本地参数 | `.env` |
| 修改默认参数和新增环境变量 | `src/fundlab/config.py`、`.env.example` |
| AKShare 字段变化 | `src/fundlab/providers/akshare_provider.py` |
| 新数据源 | `src/fundlab/providers/` |
| 收益和风险公式 | `src/fundlab/analytics/`，同时修改测试 |
| 状态阈值 | `src/fundlab/rules/decision.py` |
| DeepSeek 请求 | `src/fundlab/ai/providers/deepseek.py` |
| AI 输出 Schema | `src/fundlab/domain/models.py` |
| AI Prompt | `prompts/`，同时提高 Prompt 版本 |
| 数据库表 | `src/fundlab/storage/schema.py`，正式升级时增加迁移 |
| 页面 | `app.py`、`pages/` |

## 分支和提交

- `main` 保持可运行；
- 功能分支使用 `feature/<name>`；
- Provider 修复使用 `fix/provider-<name>`；
- 公式、Prompt 和依赖升级使用独立提交；
- 提交前运行 Ruff、测试和敏感信息检查。

## 新增 Provider

实现 `FundDataProvider`：

```python
class NewProvider:
    name = "new_provider"
    def get_fund_profile(self, fund_code): ...
    def get_nav_history(self, fund_code, start_date=None, end_date=None): ...
    def health_check(self): ...
```

将上游原始字段转换为 `FundProfile` 和 `NavRecord`，不要把上游 DataFrame 传入页面。

## 新增 AI 供应商

实现 `LLMProvider.generate_structured`，返回 `LLMResult`。业务层不能导入供应商 SDK，也不能把供应商响应对象泄露到领域层。

