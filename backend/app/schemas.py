from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BucketKey = Literal["defense", "core", "satellite"]
FundType = Literal[
    "money", "deposit_index", "bond", "index", "active_equity", "mixed",
    "qdii", "commodity", "fof", "reit", "unsupported", "unknown",
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PortfolioUpdate(BaseModel):
    capital_budget: float = Field(ge=100, le=100_000_000)
    name: str = Field(default="我的实验组合", min_length=1, max_length=120)


class FundEnsure(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(default="", max_length=240)
    fund_type: FundType = "unknown"


class HoldingInput(BaseModel):
    fund_code: str = Field(pattern=r"^\d{6}$")
    fund_name: str = Field(default="", max_length=240)
    amount: float = Field(gt=0)
    displayed_profit: float | None = None
    bucket: BucketKey | None = None


class SnapshotCreate(BaseModel):
    as_of_date: date
    completeness: Literal["complete", "partial"] = "complete"
    source: Literal["manual", "ocr"] = "manual"
    note: str = Field(default="", max_length=1000)
    items: list[HoldingInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_codes(self):
        codes = [item.fund_code for item in self.items]
        if len(codes) != len(set(codes)):
            raise ValueError("同一快照不能重复出现同一基金代码")
        return self


class BucketAssignmentUpdate(BaseModel):
    bucket: BucketKey
    note: str = Field(default="", max_length=500)


class EvidenceCreate(BaseModel):
    fund_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    evidence_kind: Literal["announcement", "news", "manual"] = "manual"
    title: str = Field(min_length=2, max_length=320)
    source_url: str = Field(min_length=8, max_length=3000)
    source_level: Literal["S", "A", "B", "C"] = "B"
    published_at: date
    content: str = Field(default="", max_length=30_000)
    event_type: Literal[
        "liquidation", "merger", "redemption_suspension", "contract_termination",
        "manager_departure", "index_rule_change", "regulatory_change", "other",
    ] = "other"
    verified: bool = False


class ReviewDecisionCreate(BaseModel):
    user_choice: Literal["agree", "reject", "defer"]
    note: str = Field(default="", max_length=1000)


class AiSettingsUpdate(BaseModel):
    enabled: bool
    api_key: str | None = Field(default=None, max_length=512)
    clear_api_key: bool = False
    base_url: str = Field(default="https://api.deepseek.com", min_length=8, max_length=500)
    model: str = Field(default="deepseek-v4-flash", min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._:/-]+$")

    @field_validator("api_key")
    @classmethod
    def clean_key(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value is not None else None
        return cleaned or None

    @field_validator("base_url")
    @classmethod
    def safe_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlsplit(cleaned)
        local_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not local_http:
            raise ValueError("Base URL 必须使用 HTTPS；本机 localhost 可使用 HTTP")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL 格式不安全")
        return cleaned

    @model_validator(mode="after")
    def key_action_is_unambiguous(self):
        if self.api_key and self.clear_api_key:
            raise ValueError("不能同时填写和清除 API Key")
        return self


class ImportItemUpdate(BaseModel):
    fund_code: str = Field(pattern=r"^\d{6}$")
    fund_name: str = Field(default="", max_length=240)
    amount: float = Field(gt=0)
    displayed_profit: float | None = None
    bucket: BucketKey


class ImportConfirm(BaseModel):
    as_of_date: date
    completeness: Literal["complete", "partial"] = "complete"
    items: list[ImportItemUpdate] = Field(min_length=1, max_length=100)


class AiEvidencePoint(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(max_length=20)


class AiExplanation(BaseModel):
    summary: str
    supporting_points: list[AiEvidencePoint]
    counterpoints: list[AiEvidencePoint]
    unknowns: list[str]


class FundRead(ORMModel):
    id: int
    code: str
    name: str
    share_class: str
    fund_type: str
    subtype: str
    peer_key: str
    default_bucket: str
    benchmark: str
    tracked_index: str
    currency: str
    valuation_lag_note: str
    target_risk: str
    product_status: str
    tracking_error: float | None
    return_method: str
    manager: str
    purchase_status: str
    redemption_status: str
    inception_date: date | None
    aum_yi: float | None
    expense_ratio: float | None
    peer_percentile: float | None
    source_name: str
    source_url: str
    value_date: date | None
    fetched_at: datetime | None
    quality_status: str
