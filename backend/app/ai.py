from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .config import Settings
from .schemas import AiExplanation

AI_PROMPT_VERSION = "v2.1.2"
AI_SCHEMA_VERSION = "v2.1.1"


def ai_configuration_status(settings: Settings) -> dict:
    missing: list[str] = []
    if not settings.ai_enabled:
        missing.append("FUNDLAB_AI_ENABLED=true")
    if not settings.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    if not settings.deepseek_model:
        missing.append("DEEPSEEK_MODEL")
    status = "disabled" if not settings.ai_enabled else "incomplete" if missing else "configured"
    return {
        "status": status,
        "enabled": settings.ai_enabled,
        "key_configured": bool(settings.deepseek_api_key),
        "model": settings.deepseek_model or None,
        "base_url": settings.deepseek_base_url,
        "missing": missing,
        "environment_overrides": [
            name for name in ("FUNDLAB_AI_ENABLED", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL")
            if name in os.environ
        ],
    }


def _configuration_error(settings: Settings) -> dict | None:
    configuration = ai_configuration_status(settings)
    if configuration["status"] == "disabled":
        return {"ok": True, "status": "disabled", "provider": "disabled", "message": "AI 未启用，确定性评估可完整运行"}
    if configuration["status"] == "incomplete":
        return {"ok": False, "status": "configuration_error", "provider": "deepseek", "message": "请在本机 .env 同时配置 API Key 和模型名"}
    return None


async def test_deepseek(settings: Settings) -> dict:
    configuration = _configuration_error(settings)
    if configuration is not None:
        return configuration
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": "只返回 JSON。"},
            {"role": "user", "content": "返回 {\"status\":\"ok\"}。"},
        ],
        "temperature": 0,
        "max_tokens": 30,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            json.loads(response.json()["choices"][0]["message"]["content"])
        return {"ok": True, "status": "ok", "provider": "deepseek", "model": settings.deepseek_model, "message": "连接和 JSON 输出正常"}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "status": "failed", "provider": "deepseek", "model": settings.deepseek_model, "message": f"DeepSeek 返回 HTTP {exc.response.status_code}，请检查 Key、余额或模型权限"}
    except httpx.RequestError:
        return {"ok": False, "status": "failed", "provider": "deepseek", "model": settings.deepseek_model, "message": "无法连接 DeepSeek，请检查网络和 Base URL"}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {"ok": False, "status": "failed", "provider": "deepseek", "model": settings.deepseek_model, "message": "DeepSeek 已响应，但返回内容不是有效 JSON"}


async def explain_review(settings: Settings, review: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    configuration = _configuration_error(settings)
    if configuration is not None:
        return {"status": "disabled" if configuration["ok"] else "configuration_error", "summary": configuration["message"], "supporting_points": [], "counterpoints": [], "unknowns": []}
    valid_ids = {item["evidence_id"] for item in evidence}
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你只解释给定的确定性基金复核结果与 Evidence Pack。不得修改 verdict、动作、数字或仓位；"
                    "不得使用包外当前事实。量化结论可以使用空 evidence_ids；涉及公告或事件的陈述必须引用包内 evidence_id。"
                    "输出 JSON：summary、supporting_points、counterpoints、unknowns。"
                    "supporting_points 和 counterpoints 每项必须包含 text 与 evidence_ids。没有文档证据时要明确说明。"
                ),
            },
            {"role": "user", "content": json.dumps({"review": review, "evidence_pack": evidence}, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            parsed = json.loads(response.json()["choices"][0]["message"]["content"])
        validated = AiExplanation.model_validate(parsed)
        result = validated.model_dump()
        for group in ("supporting_points", "counterpoints"):
            for point in result[group]:
                if any(item not in valid_ids for item in point.get("evidence_ids", [])):
                    raise ValueError("模型引用 Evidence Pack 外的证据")
        return {"status": "ok", **result}
    except Exception:
        return {"status": "failed", "summary": "AI 解释失败，确定性结果不受影响。", "supporting_points": [], "counterpoints": [], "unknowns": ["请检查模型、网络或结构化输出"]}
