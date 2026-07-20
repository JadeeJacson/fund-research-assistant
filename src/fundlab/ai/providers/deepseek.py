from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from fundlab.ai.cache import FileAICache
from fundlab.config import Settings
from fundlab.domain.models import LLMResult, TokenUsage

Transport = Callable[[str, dict[str, str], bytes, float], dict[str, Any]]


def _default_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> dict[str, Any]:
    request = Request(url=url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL 来自受控配置
        return json.loads(response.read().decode("utf-8"))


class DeepSeekProvider:
    """DeepSeek Chat Completions 适配器。

    默认使用 v4-flash 和官方 JSON Output。模型、URL、预算与价格全部从 .env 读取，
    因此 DeepSeek 后续升级时通常只需修改配置或本文件。
    """

    name = "deepseek"

    def __init__(
        self,
        settings: Settings,
        cache: FileAICache,
        *,
        transport: Transport | None = None,
    ):
        if not settings.deepseek_api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY")
        self.settings = settings
        self.cache = cache
        self.transport = transport or _default_transport
        self.model = settings.deepseek_model

    def health_check(self) -> tuple[bool, str]:
        return True, f"DeepSeek 配置完成，模型：{self.model}"

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        output_model: type[BaseModel],
        *,
        cache_context: dict[str, Any] | None = None,
    ) -> LLMResult:
        cache_payload = {
            "provider": self.name,
            "model": self.model,
            "messages": messages,
            "schema": output_model.model_json_schema(),
            "thinking": self.settings.deepseek_thinking,
        }
        cache_key = self.cache.make_key(cache_payload)
        cached = self.cache.get(cache_key)
        if cached is not None:
            validated = output_model.model_validate(cached["data"])
            return LLMResult(
                data=validated.model_dump(mode="json"),
                provider=self.name,
                model=self.model,
                usage=TokenUsage.model_validate(cached.get("usage", {})),
                latency_ms=0,
                cached=True,
            )

        request_payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": self.settings.deepseek_max_tokens,
            "stream": False,
            # 明确关闭/开启思考，避免供应商默认值变化影响行为。
            "thinking": {"type": "enabled" if self.settings.deepseek_thinking else "disabled"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")

        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.settings.deepseek_max_retries + 1):
            try:
                response = self.transport(
                    f"{self.settings.deepseek_base_url}/chat/completions",
                    headers,
                    body,
                    self.settings.deepseek_timeout_seconds,
                )
                content = response["choices"][0]["message"].get("content", "")
                if not content or not content.strip():
                    raise ValueError("DeepSeek 返回了空内容")
                raw_data = json.loads(content)
                validated = output_model.model_validate(raw_data)
                usage_raw = response.get("usage", {})
                prompt_tokens = int(usage_raw.get("prompt_tokens", 0) or 0)
                completion_tokens = int(usage_raw.get("completion_tokens", 0) or 0)
                estimated_cost = (
                    prompt_tokens * self.settings.deepseek_input_price_per_million_usd / 1_000_000
                    + completion_tokens
                    * self.settings.deepseek_output_price_per_million_usd
                    / 1_000_000
                )
                usage = TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=int(
                        usage_raw.get("total_tokens", prompt_tokens + completion_tokens) or 0
                    ),
                    estimated_cost_usd=estimated_cost,
                )
                result = LLMResult(
                    data=validated.model_dump(mode="json"),
                    provider=self.name,
                    model=self.model,
                    usage=usage,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                self.cache.set(
                    cache_key,
                    {"data": result.data, "usage": usage.model_dump(mode="json")},
                )
                return result
            except (
                HTTPError,
                URLError,
                TimeoutError,
                json.JSONDecodeError,
                ValidationError,
                KeyError,
                ValueError,
            ) as exc:
                last_error = exc
                if attempt < self.settings.deepseek_max_retries:
                    time.sleep(min(2**attempt, 4))
                    continue
                break
        raise RuntimeError(f"DeepSeek 结构化调用失败：{last_error}") from last_error
