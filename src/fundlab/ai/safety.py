from __future__ import annotations

from datetime import date

from fundlab.domain.models import AIAnalysis, EvidenceItem


class AIValidationError(ValueError):
    pass


def validate_ai_analysis(
    analysis: AIAnalysis,
    evidence: list[EvidenceItem],
    *,
    expected_subject_id: str,
    as_of_date: date,
) -> AIAnalysis:
    """执行模型输出后的确定性安全检查。"""

    if analysis.subject_id != expected_subject_id:
        raise AIValidationError("模型返回了错误的分析对象")
    if analysis.as_of_date != as_of_date:
        raise AIValidationError("模型返回了错误的分析截止日期")

    allowed_ids = {item.evidence_id for item in evidence}
    future_ids = {item.evidence_id for item in evidence if item.published_at.date() > as_of_date}
    for event in analysis.events:
        unknown = set(event.evidence_ids) - allowed_ids
        if unknown:
            raise AIValidationError(f"模型引用了不存在的证据：{sorted(unknown)}")
        leaked = set(event.evidence_ids) & future_ids
        if leaked:
            raise AIValidationError(f"模型引用了截止日期后的证据：{sorted(leaked)}")
    return analysis
