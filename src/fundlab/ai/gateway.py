from __future__ import annotations

from fundlab.ai.cache import FileAICache
from fundlab.ai.providers import DeepSeekProvider, MockLLMProvider
from fundlab.config import Settings
from fundlab.domain.protocols import LLMProvider


def build_llm_provider(settings: Settings, *, force_mock: bool = False) -> LLMProvider:
    """按配置创建 AI Provider；未启用或无 Key 时安全降级为 Mock。"""

    if force_mock or not settings.ai_enabled or not settings.deepseek_api_key:
        return MockLLMProvider()
    return DeepSeekProvider(settings, FileAICache(settings.ai_cache_dir))
