from __future__ import annotations

from datetime import date

from fundlab.domain.enums import AnalysisState, FundType
from fundlab.domain.models import FundProfile, MetricSet, RuleDecision


def build_decision(
    fund: FundProfile,
    metrics: MetricSet,
    *,
    risk_tolerance: float,
    validation_warnings: list[str] | None = None,
    today: date | None = None,
) -> RuleDecision:
    """透明、可测试的启发式规则。

    分数不是收益预测，只用于把证据整理成一致的界面状态。阈值集中在本函数，
    未来应根据实际使用和样本外评估校准。
    """

    warnings = list(validation_warnings or [])
    positive: list[str] = []
    risks: list[str] = []
    unknowns: list[str] = []
    triggered: list[str] = []
    research = 50
    personal_fit = 80

    history_days = (metrics.end_date - metrics.start_date).days
    stale_days = ((today or date.today()) - metrics.end_date).days
    if metrics.observations < 200 or history_days < 365:
        triggered.append("DATA_HISTORY_LT_1Y")
        return RuleDecision(
            research_score=40,
            personal_fit_score=30,
            data_confidence="C",
            state=AnalysisState.INSUFFICIENT_DATA,
            risk_reasons=warnings,
            unknowns=["历史数据不足一年，暂不生成强结论"],
            triggered_rules=triggered,
        )

    if stale_days > 14:
        risks.append(f"净值已滞后 {stale_days} 天")
        research -= 10
        triggered.append("DATA_STALE")

    if metrics.annualized_return > 0:
        research += 8
        positive.append("分析区间年化收益为正")
    else:
        research -= 8
        risks.append("分析区间年化收益为负")

    if metrics.sharpe_ratio is not None and metrics.sharpe_ratio >= 0.5:
        research += 10
        positive.append("历史风险调整收益相对较好")
    elif metrics.sharpe_ratio is not None and metrics.sharpe_ratio < 0:
        research -= 10
        risks.append("历史风险调整收益为负")

    drawdown = abs(metrics.max_drawdown)
    if drawdown <= risk_tolerance:
        research += 8
        personal_fit += 10
        positive.append("历史最大回撤未超过当前参考线")
    else:
        excess_ratio = drawdown / max(risk_tolerance, 1e-6)
        penalty = min(60, int((excess_ratio - 1) * 35 + 15))
        personal_fit -= penalty
        risks.append(f"历史最大回撤 {drawdown:.1%} 超过账户参考线 {risk_tolerance:.1%}")
        triggered.append("RISK_DRAWDOWN_OVER_BUDGET")

    if fund.fund_type == FundType.UNKNOWN:
        research -= 10
        personal_fit -= 10
        unknowns.append("基金类型未可靠识别，专属评价模块未启用")
        triggered.append("FUND_TYPE_UNKNOWN")

    research = max(0, min(100, research))
    personal_fit = max(0, min(100, personal_fit))
    confidence = "A" if history_days >= 3 * 365 and stale_days <= 14 else "B"

    if personal_fit < 45:
        state = AnalysisState.NOT_SUITABLE
    elif research >= 65 and personal_fit >= 65:
        state = AnalysisState.REBALANCE_CANDIDATE
    elif research < 45:
        state = AnalysisState.HOLD_REVIEW
    else:
        state = AnalysisState.WATCH

    return RuleDecision(
        research_score=research,
        personal_fit_score=personal_fit,
        data_confidence=confidence,
        state=state,
        positive_reasons=positive,
        risk_reasons=risks + warnings,
        unknowns=unknowns,
        triggered_rules=triggered,
    )
