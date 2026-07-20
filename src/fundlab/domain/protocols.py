from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from pydantic import BaseModel

from .models import FundProfile, LLMResult, NavRecord


class FundDataProvider(Protocol):
    name: str

    def get_fund_profile(self, fund_code: str) -> FundProfile: ...

    def get_nav_history(
        self, fund_code: str, start_date: date | None = None, end_date: date | None = None
    ) -> list[NavRecord]: ...

    def health_check(self) -> tuple[bool, str]: ...


class LLMProvider(Protocol):
    name: str

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        output_model: type[BaseModel],
        *,
        cache_context: dict[str, Any] | None = None,
    ) -> LLMResult: ...

    def health_check(self) -> tuple[bool, str]: ...
