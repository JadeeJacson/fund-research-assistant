# 数据和交易流水导入

## 基金净值

默认通过 AKShare 获取开放式基金净值。若上游失效，可以使用 `ManualCsvProvider`，格式：

```csv
nav_date,unit_nav,accumulated_nav,adjusted_nav
2025-01-02,1.0000,,
2025-01-03,1.0020,,
```

- `nav_date`、`unit_nav` 必填；
- `accumulated_nav`、`adjusted_nav` 可选；
- 有可靠复权总回报数据时优先填 `adjusted_nav`；
- 系统不会默默修复超过 20% 的单日跳变，而会提示核验分红、拆分或数据错误。

## 支付宝交易流水

不要提供支付宝密码或 Cookie。请人工整理或从自己的合法记录转换为 CSV：

```csv
account,fund_code,share_class,trade_date,action,amount,shares,nav,fee,dividend,source
支付宝,000001,A,2026-01-05,buy,1000,980.392157,1.02,0,0,manual
```

字段：

| 字段 | 说明 |
| --- | --- |
| `account` | 账户标签，可使用匿名名称 |
| `fund_code` | 六位基金代码 |
| `share_class` | A、C 或 default |
| `trade_date` | 交易确认日期 |
| `action` | 下表中的操作类型 |
| `amount` | 交易金额 |
| `shares` | 份额变化的绝对值 |
| `nav` | 确认净值，可为空 |
| `fee` | 手续费 |
| `dividend` | 现金分红 |
| `source` | manual、statement 等来源标签 |

支持的 `action`：

- `buy`
- `sell`
- `dividend_cash`
- `dividend_reinvest`
- `transfer_in`
- `transfer_out`
- `adjustment`

导入：

```powershell
fundlab import-transactions data/private/portfolio_transactions.csv
```

相同记录再次导入会根据内容哈希识别为重复，不重复入库。

## 公告和新闻证据

在 Streamlit 的“AI 证据”页面填写：

- 基金代码和份额类别；
- 原始来源名称；
- 来源 URL；
- 实际发布时间；
- 文档类型和可信等级；
- 正文。

系统按段落生成 `evidence_id`。AI 只能引用这些 ID，并且不能使用分析截止日期之后的证据。

