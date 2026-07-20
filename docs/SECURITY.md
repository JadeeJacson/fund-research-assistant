# 安全与隐私

## 禁止提交

- `.env`
- `.streamlit/secrets.toml`
- `data/private/`
- SQLite 数据库
- 支付宝交易明细
- DeepSeek/Tushare API Key
- Cookie、密码和浏览器会话

## AI 数据最小化

发送给模型的内容限于公开公告、新闻、政策、证据段落和匿名化量化摘要。默认不发送账户金额、持仓成本、交易时间、账户标签或身份信息。

## Prompt Injection

外部文档被包装为 Evidence Pack，不作为系统指令。DeepSeek 无权读取文件、数据库、网络工具或密钥。模型返回后必须检查引用 ID、分析对象和截止日期。

## 发现密钥泄露

1. 立即在供应商控制台撤销 Key；
2. 创建新 Key；
3. 清理本地文件；
4. 如果进入 Git 历史，除更换 Key 外还要清理历史；
5. 检查 API 用量和异常调用。

