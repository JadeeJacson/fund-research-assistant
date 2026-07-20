from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from fundlab.domain.models import LLMResult, TokenUsage


class MockLLMProvider:
    """离线和 CI 使用的确定性模型替身，不会访问网络。"""

    name = "mock"
    model = "mock-evidence-analyzer-v1"

    def health_check(self) -> tuple[bool, str]:
        return True, "Mock Provider 可用（不会调用真实 API）"

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        output_model: type[BaseModel],
        *,
        cache_context: dict[str, Any] | None = None,
    ) -> LLMResult:
        context = cache_context or {}
        evidence_ids = list(context.get("evidence_ids", []))
        payload: dict[str, Any] = {
            "subject_id": context.get("subject_id", "unknown"),
            "as_of_date": context.get("as_of_date"),
            "summary": "当前为 Mock 模式：已验证证据管道，但未调用真实大模型。",
            "events": [],
            "risk_flags": ["mock_mode"],
            "unknowns": ["需要启用 DeepSeek API 才能生成真实文本分析"],
        }
        if evidence_ids:
            payload["events"] = [
                {
                    "event_type": "mock_evidence_review",
                    "direction": "uncertain",
                    "impact_horizon": "unknown",
                    "confidence": 0.0,
                    "evidence_ids": [evidence_ids[0]],
                    "reasoning_summary": "Mock 模式不判断事件方向。",
                    "counterarguments": [],
                    "invalidating_conditions": [],
                }
            ]
        validated = output_model.model_validate(payload)
        return LLMResult(
            data=validated.model_dump(mode="json"),
            provider=self.name,
            model=self.model,
            usage=TokenUsage(),
        )
