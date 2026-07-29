from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings


async def test_deepseek(settings: Settings) -> dict:
    if not settings.ai_enabled:
        return {"ok": True, "provider": "mock", "message": "AI 未启用，确定性功能可正常使用"}
    if not settings.deepseek_api_key or not settings.deepseek_model:
        return {
            "ok": False,
            "provider": "deepseek",
            "message": "请同时配置 DEEPSEEK_API_KEY 和 DEEPSEEK_MODEL",
        }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": "只返回 JSON。"},
            {"role": "user", "content": "返回 {\"status\":\"ok\"}，不要包含任何其他内容。"},
        ],
        "temperature": 0,
        "max_tokens": 30,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
        return {
            "ok": True,
            "provider": "deepseek",
            "model": settings.deepseek_model,
            "message": "连接与最小 JSON 响应正常",
        }
    except Exception:
        return {
            "ok": False,
            "provider": "deepseek",
            "model": settings.deepseek_model,
            "message": "连接或结构化响应校验失败，请检查配置后重试",
        }


async def explain_report(
    settings: Settings,
    report: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    if not evidence:
        return {
            "status": "insufficient_evidence",
            "summary": "尚未提供可引用证据，未生成 AI 解释。",
            "supporting_points": [],
            "counterpoints": [],
            "unknowns": ["请先添加官方披露或可靠媒体证据"],
        }
    if not settings.ai_enabled:
        return {
            "status": "mock",
            "summary": "AI 未启用；已保留确定性结论和证据清单。",
            "supporting_points": [
                {"text": "证据已进入 Evidence Pack，启用 AI 后可生成结构化解释", "evidence_ids": [evidence[0]["evidence_id"]]}
            ],
            "counterpoints": [{"text": "当前未由模型评估证据影响方向", "evidence_ids": []}],
            "unknowns": ["DeepSeek 未启用"],
        }
    if not settings.deepseek_api_key or not settings.deepseek_model:
        return {
            "status": "configuration_error",
            "summary": "DeepSeek 配置不完整。",
            "supporting_points": [],
            "counterpoints": [],
            "unknowns": ["缺少 API Key 或模型名"],
        }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你只解释给定基金研究结果和 Evidence Pack。不得修改核心数字、操作状态或仓位区间；"
                    "不得使用包外当前事实。输出 JSON，字段为 summary、supporting_points、"
                    "counterpoints、unknowns；每个观点的 evidence_ids 只能引用提供的 ID。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"report": report, "evidence_pack": evidence},
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
    }
    valid_ids = {item["evidence_id"] for item in evidence}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
        for group in ("supporting_points", "counterpoints"):
            for point in parsed.get(group, []):
                ids = point.get("evidence_ids", [])
                if any(item not in valid_ids for item in ids):
                    raise ValueError("模型引用了 Evidence Pack 外的证据")
        return {"status": "ok", **parsed}
    except Exception:
        return {
            "status": "failed",
            "summary": "AI 解释生成失败，确定性结论不受影响。",
            "supporting_points": [],
            "counterpoints": [],
            "unknowns": ["请检查模型配置、网络或结构化输出后重试"],
        }
