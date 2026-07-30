from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CandidateCreate(BaseModel):
    fund_code: str = Field(pattern=r"^\d{6}$")
    fund_name: str = Field(default="", max_length=200)
    share_class: str = Field(default="", max_length=8)
    fund_type: Literal["index", "active_equity", "bond", "unsupported", "unknown"] = "unknown"
    note: str = Field(default="", max_length=1000)
    planned_amount: float | None = Field(default=None, ge=0)


class CandidateRead(ORMModel):
    id: int
    fund_code: str
    fund_name: str
    share_class: str
    fund_type: str
    note: str
    planned_amount: float | None
    latest_nav: float | None
    nav_date: date | None
    data_source: str
    refreshed_at: datetime | None
    created_at: datetime


class HoldingCreate(BaseModel):
    fund_code: str = Field(pattern=r"^\d{6}$")
    fund_name: str = Field(min_length=1, max_length=200)
    amount: float = Field(ge=0)
    weight: float | None = Field(default=None, ge=0, le=1)
    holding_profit: float | None = None
    snapshot_date: date
    source: str = "人工录入"


class HoldingRead(HoldingCreate, ORMModel):
    id: int
    created_at: datetime


class TransactionCreate(BaseModel):
    fund_code: str = Field(pattern=r"^\d{6}$")
    fund_name: str = Field(min_length=1, max_length=200)
    action: Literal["buy", "sell", "convert_in", "convert_out", "dividend", "adjustment"]
    amount: float | None = Field(default=None, ge=0)
    shares: float | None = Field(default=None, ge=0)
    nav: float | None = Field(default=None, gt=0)
    fee: float | None = Field(default=None, ge=0)
    trade_time: datetime
    source: str = "人工录入"

    @model_validator(mode="after")
    def amount_or_shares(self):
        if self.amount is None and self.shares is None:
            raise ValueError("金额和份额至少填写一项")
        return self


class TransactionRead(TransactionCreate, ORMModel):
    id: int
    created_at: datetime


class ImportItemUpdate(BaseModel):
    kind: Literal["candidate", "holding", "transaction"]
    fund_code: str = Field(default="", pattern=r"^$|^\d{6}$")
    fund_name: str = Field(default="", max_length=200)
    action: str = Field(default="", max_length=24)
    amount: float | None = Field(default=None, ge=0)
    shares: float | None = Field(default=None, ge=0)
    event_time: datetime | None = None


class ImportItemRead(ORMModel):
    id: int
    kind: str
    fund_code: str
    fund_name: str
    action: str
    amount: float | None
    shares: float | None
    event_time: datetime | None
    confidence: float
    issues: str
    confirmed: bool


class ImportBatchRead(ORMModel):
    id: int
    filename: str
    page_type: str
    raw_text: str
    status: str
    error: str
    created_at: datetime
    items: list[ImportItemRead]


class ReportRequest(BaseModel):
    candidate_id: int
    horizon: Literal["short", "long"]


class EvidenceCreate(BaseModel):
    candidate_id: int
    title: str = Field(min_length=2, max_length=240)
    source_url: str = Field(min_length=8, max_length=2000)
    published_at: date
    trust_level: Literal["S", "A", "B", "C"] = "B"
    content: str = Field(min_length=10, max_length=12000)


class EvidenceRead(EvidenceCreate, ORMModel):
    id: int
    created_at: datetime


class TriggerCreate(BaseModel):
    candidate_id: int
    metric: Literal["latest_nav", "drawdown", "annualized_return", "volatility"]
    operator: Literal["<", "<=", ">", ">="]
    threshold: float


class TriggerRead(ORMModel):
    id: int
    candidate_id: int
    metric: str
    operator: str
    threshold: float
    enabled: bool
    last_value: float | None
    last_matched: bool | None
    checked_at: datetime | None
