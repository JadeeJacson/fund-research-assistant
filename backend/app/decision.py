from __future__ import annotations

from dataclasses import dataclass

from .analytics import Metrics


SUPPORTED_TYPES = {"index", "active_equity", "bond"}


@dataclass(frozen=True, slots=True)
class DecisionContext:
    fund_name: str
    fund_type: str
    horizon: str
    current_weight: float
    data_source: str
    risk_tolerance: float


def _target_range(
    fund_name: str, fund_type: str, favorable: bool, horizon: str
) -> tuple[float, float, str]:
    theme_words = ("芯片", "机器人", "互联网", "人工智能", "半导体", "医药", "新能源")
    exposure = next((word for word in theme_words if word in fund_name), "")
    base = {
        "index": (0.08, 0.18),
        "active_equity": (0.05, 0.12),
        "bond": (0.15, 0.30),
    }.get(fund_type, (0.0, 0.0))
    if exposure:
        base = (0.03, 0.08)
    if not favorable:
        base = (base[0] * 0.5, base[1] * 0.6)
    if horizon == "short":
        base = (base[0] * 0.65, base[1] * 0.7)
    return round(base[0], 3), round(base[1], 3), exposure or "非单一主题"


def build_decision(metrics: Metrics, context: DecisionContext) -> dict:
    if context.fund_type not in SUPPORTED_TYPES:
        return {
            "state": "暂不支持完整评价",
            "target_weight": [0, 0],
            "confidence": "低",
            "positive_points": [],
            "risk_points": ["该基金类型超出 MVP 的完整评价范围"],
            "unknowns": ["需要相应资产类别的专属数据与规则"],
            "triggers": [],
            "valid_days": 5,
        }
    if metrics.observations < 120:
        return {
            "state": "数据不足",
            "target_weight": [0, 0],
            "confidence": "低",
            "positive_points": [],
            "risk_points": ["有效净值不足 120 个观察值"],
            "unknowns": ["长期风险和回撤尚无法可靠估计"],
            "triggers": [],
            "valid_days": 5,
        }

    drawdown = abs(metrics.max_drawdown or 0)
    horizon_return = metrics.return_3m if context.horizon == "short" else metrics.return_1y
    favorable = (horizon_return or 0) > 0 and drawdown <= context.risk_tolerance * 1.5
    target_low, target_high, exposure = _target_range(
        context.fund_name, context.fund_type, favorable, context.horizon
    )
    positive: list[str] = []
    risks: list[str] = []
    unknowns: list[str] = []
    if (horizon_return or 0) > 0:
        positive.append("当前期限对应的历史收益为正")
    else:
        risks.append("当前期限对应的历史收益未转正")
    if drawdown <= context.risk_tolerance:
        positive.append("样本内最大回撤未超过 10% 风险参考线")
    else:
        risks.append(
            f"样本内最大回撤 {drawdown:.1%} 超过 {context.risk_tolerance:.0%} 风险参考线"
        )
    if metrics.volatility is not None and metrics.volatility > 0.28:
        risks.append(f"年化波动率约 {metrics.volatility:.1%}，仓位应受限")
        target_high *= 0.75
    if "演示" in context.data_source:
        unknowns.append("当前使用离线演示数据，实际投资前必须刷新公开数据")
    if exposure != "非单一主题":
        risks.append(f"识别为“{exposure}”主题暴露，单主题目标上限被约束为 8%")

    if context.current_weight == 0:
        state = "建仓候选" if favorable else "继续观察"
    elif context.current_weight < target_low and favorable:
        state = "小幅加仓候选"
    elif context.current_weight > target_high:
        state = "减仓候选"
    elif drawdown > context.risk_tolerance * 1.8:
        state = "退出复核"
    elif favorable:
        state = "继续持有"
    else:
        state = "暂停加仓"

    valid_days = 7 if context.horizon == "short" else 30
    triggers = [
        {
            "metric": "drawdown",
            "operator": "<=",
            "threshold": -context.risk_tolerance,
            "description": "回撤进入风险参考区间时重新评估基本假设",
        },
        {
            "metric": "latest_nav",
            "operator": "<=",
            "threshold": round((1 - context.risk_tolerance) * 100, 2),
            "description": "示例相对阈值；需结合估值分位，不能只凭单位净值买入",
            "normalized": True,
        },
    ]
    return {
        "state": state,
        "target_weight": [round(target_low, 3), round(target_high, 3)],
        "exposure_bucket": exposure,
        "confidence": "中" if unknowns else "高",
        "positive_points": positive,
        "risk_points": risks,
        "unknowns": unknowns,
        "triggers": triggers,
        "valid_days": valid_days,
        "disclaimer": "10% 为阶段性风险参考，不是止损成交价或未来损失上限。",
    }
