from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Fund(Base):
    __tablename__ = "v2_funds"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    share_class: Mapped[str] = mapped_column(String(16), default="")
    fund_type: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    subtype: Mapped[str] = mapped_column(String(80), default="")
    peer_key: Mapped[str] = mapped_column(String(120), default="")
    default_bucket: Mapped[str] = mapped_column(String(16), default="satellite")
    benchmark: Mapped[str] = mapped_column(String(240), default="")
    tracked_index: Mapped[str] = mapped_column(String(240), default="")
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    valuation_lag_note: Mapped[str] = mapped_column(String(240), default="")
    target_risk: Mapped[str] = mapped_column(String(80), default="")
    product_status: Mapped[str] = mapped_column(String(48), default="active")
    tracking_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_method: Mapped[str] = mapped_column(String(120), default="cumulative_nav")
    manager: Mapped[str] = mapped_column(String(160), default="")
    purchase_status: Mapped[str] = mapped_column(String(40), default="unknown")
    redemption_status: Mapped[str] = mapped_column(String(40), default="unknown")
    inception_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    aum_yi: Mapped[float | None] = mapped_column(Float, nullable=True)
    expense_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    peer_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_name: Mapped[str] = mapped_column(String(100), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(24), default="limited")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NavPoint(Base):
    __tablename__ = "v2_nav_points"
    __table_args__ = (UniqueConstraint("fund_id", "nav_date", name="uq_v2_nav"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("v2_funds.id", ondelete="CASCADE"), index=True)
    nav_date: Mapped[date] = mapped_column(Date)
    unit_nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    cumulative_nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_name: Mapped[str] = mapped_column(String(100))
    quality_status: Mapped[str] = mapped_column(String(24), default="limited")


class PeerMetricPoint(Base):
    __tablename__ = "v2_peer_metric_points"
    __table_args__ = (UniqueConstraint("fund_id", "metric_date", name="uq_v2_peer_metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("v2_funds.id", ondelete="CASCADE"), index=True)
    metric_date: Mapped[date] = mapped_column(Date)
    percentile: Mapped[float] = mapped_column(Float)
    source_name: Mapped[str] = mapped_column(String(100))


class ProviderSnapshot(Base):
    __tablename__ = "v2_provider_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int | None] = mapped_column(ForeignKey("v2_funds.id", ondelete="CASCADE"), nullable=True)
    provider: Mapped[str] = mapped_column(String(80))
    data_kind: Mapped[str] = mapped_column(String(48))
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    quality_status: Mapped[str] = mapped_column(String(24))
    payload_json: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    error: Mapped[str] = mapped_column(Text, default="")


class Portfolio(Base):
    __tablename__ = "v2_portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(120), default="我的实验组合")
    capital_budget: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class HoldingSnapshot(Base):
    __tablename__ = "v2_holding_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("v2_portfolios.id"), default=1)
    as_of_date: Mapped[date] = mapped_column(Date)
    total_market_value: Mapped[float] = mapped_column(Float)
    completeness: Mapped[str] = mapped_column(String(24), default="complete")
    source: Mapped[str] = mapped_column(String(40), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list[HoldingItem]] = relationship(cascade="all, delete-orphan", order_by="HoldingItem.id")


class HoldingItem(Base):
    __tablename__ = "v2_holding_items"
    __table_args__ = (UniqueConstraint("snapshot_id", "fund_id", name="uq_v2_snapshot_fund"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("v2_holding_snapshots.id", ondelete="CASCADE"), index=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("v2_funds.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    displayed_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    bucket: Mapped[str] = mapped_column(String(16))
    assignment_source: Mapped[str] = mapped_column(String(16), default="rule")
    fund: Mapped[Fund] = relationship()


class BucketAssignment(Base):
    __tablename__ = "v2_bucket_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("v2_funds.id", ondelete="CASCADE"), unique=True)
    bucket: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16), default="user")
    note: Mapped[str] = mapped_column(Text, default="")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evidence(Base):
    __tablename__ = "v2_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int | None] = mapped_column(ForeignKey("v2_funds.id", ondelete="CASCADE"), nullable=True, index=True)
    evidence_kind: Mapped[str] = mapped_column(String(24), default="announcement")
    title: Mapped[str] = mapped_column(String(320))
    source_url: Mapped[str] = mapped_column(Text)
    source_level: Mapped[str] = mapped_column(String(2), default="B")
    published_at: Mapped[date] = mapped_column(Date)
    available_from: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(48), default="other")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewRun(Base):
    __tablename__ = "v2_review_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("v2_holding_snapshots.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(16), default="review")
    data_quality: Mapped[str] = mapped_column(String(16), default="limited")
    as_of_date: Mapped[date] = mapped_column(Date)
    rule_version: Mapped[str] = mapped_column(String(32))
    rule_hash: Mapped[str] = mapped_column(String(64))
    input_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    bucket_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    headline_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list[ReviewItem]] = relationship(cascade="all, delete-orphan", order_by="ReviewItem.id")


class ReviewItem(Base):
    __tablename__ = "v2_review_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("v2_review_runs.id", ondelete="CASCADE"), index=True)
    fund_id: Mapped[int | None] = mapped_column(ForeignKey("v2_funds.id"), nullable=True)
    reason_type: Mapped[str] = mapped_column(String(32))
    proposed_action: Mapped[str] = mapped_column(String(24))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str] = mapped_column(Text)
    metric_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="open")
    fund: Mapped[Fund | None] = relationship()
    decision: Mapped[ReviewDecision | None] = relationship(cascade="all, delete-orphan", uselist=False)


class ReviewDecision(Base):
    __tablename__ = "v2_review_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("v2_review_items.id", ondelete="CASCADE"), unique=True)
    user_choice: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlternativeComparison(Base):
    __tablename__ = "v2_alternative_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("v2_review_runs.id"), nullable=True)
    current_fund_id: Mapped[int] = mapped_column(ForeignKey("v2_funds.id"), index=True)
    candidate_fund_id: Mapped[int] = mapped_column(ForeignKey("v2_funds.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    improvements_json: Mapped[str] = mapped_column(Text)
    counterpoints_json: Mapped[str] = mapped_column(Text)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    persistence_count: Mapped[int] = mapped_column(Integer, default=1)
    compared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CandidateUniverseSnapshot(Base):
    __tablename__ = "v2_candidate_universes"
    __table_args__ = (UniqueConstraint("month_key", "peer_key", name="uq_v2_universe_month_peer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    month_key: Mapped[str] = mapped_column(String(7), index=True)
    peer_key: Mapped[str] = mapped_column(String(120), index=True)
    codes_json: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiscoveryRun(Base):
    __tablename__ = "v2_discovery_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("v2_holding_snapshots.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    rule_version: Mapped[str] = mapped_column(String(32))
    rule_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportBatch(Base):
    __tablename__ = "v2_import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(240))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    image_path: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list[ImportItem]] = relationship(cascade="all, delete-orphan", order_by="ImportItem.id")


class ImportItem(Base):
    __tablename__ = "v2_import_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("v2_import_batches.id", ondelete="CASCADE"), index=True)
    fund_code: Mapped[str] = mapped_column(String(6), default="")
    fund_name: Mapped[str] = mapped_column(String(240), default="")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    displayed_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    bucket: Mapped[str] = mapped_column(String(16), default="satellite")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    bbox_json: Mapped[str] = mapped_column(Text, default="[]")
    issues: Mapped[str] = mapped_column(Text, default="")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    correction_json: Mapped[str] = mapped_column(Text, default="{}")


class AiRun(Base):
    __tablename__ = "v2_ai_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_run_id: Mapped[int] = mapped_column(ForeignKey("v2_review_runs.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="deepseek")
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="v2.1.0")
    schema_version: Mapped[str] = mapped_column(String(32), default="v2.1.0")
    status: Mapped[str] = mapped_column(String(24))
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "v2_idempotency_records"
    __table_args__ = (UniqueConstraint("operation", "idempotency_key", name="uq_v2_idempotency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    operation: Mapped[str] = mapped_column(String(80), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
