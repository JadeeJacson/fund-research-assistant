from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import (
    AnalysisState,
    DataQuality,
    Direction,
    DocumentType,
    FundType,
    ImpactHorizon,
    TransactionAction,
    TrustLevel,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FundProfile(DomainModel):
    fund_code: str = Field(min_length=6, max_length=12)
    share_class: str = "default"
    fund_name: str
    fund_type: FundType = FundType.UNKNOWN
    benchmark_code: str | None = None
    manager_name: str | None = None
    inception_date: date | None = None
    management_fee: float | None = None
    custodian_fee: float | None = None
    source: str
    fetched_at: datetime = Field(default_factory=utc_now)

    @property
    def fund_id(self) -> str:
        return f"{self.fund_code}:{self.share_class}"


class NavRecord(DomainModel):
    fund_id: str
    nav_date: date
    unit_nav: float = Field(gt=0)
    accumulated_nav: float | None = Field(default=None, gt=0)
    adjusted_nav: float | None = Field(default=None, gt=0)
    source: str
    fetched_at: datetime = Field(default_factory=utc_now)
    quality_status: DataQuality = DataQuality.OK

    @property
    def return_nav(self) -> float:
        return self.adjusted_nav or self.accumulated_nav or self.unit_nav


class TransactionRecord(DomainModel):
    account: str
    fund_code: str
    share_class: str = "default"
    trade_date: date
    action: TransactionAction
    amount: float = 0.0
    shares: float = 0.0
    nav: float | None = None
    fee: float = 0.0
    dividend: float = 0.0
    source: str = "manual"
    external_id: str | None = None


class SourceDocument(DomainModel):
    document_id: str
    document_type: DocumentType
    subject_ids: list[str]
    source_name: str
    source_url: str | None = None
    published_at: datetime
    effective_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=utc_now)
    content_hash: str
    normalized_text: str = Field(min_length=1)
    trust_level: TrustLevel = TrustLevel.OTHER


class EvidenceItem(DomainModel):
    evidence_id: str
    document_id: str
    subject_id: str
    quote: str = Field(min_length=1, max_length=1200)
    published_at: datetime
    source_name: str
    source_url: str | None = None
    trust_level: TrustLevel


class AIEvent(DomainModel):
    event_type: str
    direction: Direction
    impact_horizon: ImpactHorizon
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    reasoning_summary: str
    counterarguments: list[str] = Field(default_factory=list)
    invalidating_conditions: list[str] = Field(default_factory=list)


class AIAnalysis(DomainModel):
    subject_id: str
    as_of_date: date
    summary: str
    events: list[AIEvent] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class TokenUsage(DomainModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMResult(DomainModel):
    data: dict[str, Any]
    provider: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: int = 0
    cached: bool = False


class MetricSet(DomainModel):
    observations: int
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    annualized_volatility: float
    max_drawdown: float
    max_drawdown_days: int
    recovery_days: int | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None

    @field_validator("max_drawdown")
    @classmethod
    def drawdown_is_not_positive(cls, value: float) -> float:
        if value > 1e-12:
            raise ValueError("max_drawdown must be zero or negative")
        return value


class RuleDecision(DomainModel):
    research_score: int = Field(ge=0, le=100)
    personal_fit_score: int = Field(ge=0, le=100)
    data_confidence: str
    state: AnalysisState
    positive_reasons: list[str] = Field(default_factory=list)
    risk_reasons: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)


class FundAnalysisReport(DomainModel):
    fund: FundProfile
    metrics: MetricSet
    decision: RuleDecision
    ai_analysis: AIAnalysis | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    disclaimer: str = "本报告仅用于个人研究辅助，不构成投资建议；历史表现不代表未来收益。"
