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


class Candidate(Base):
    __tablename__ = "v1_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    fund_name: Mapped[str] = mapped_column(String(200))
    share_class: Mapped[str] = mapped_column(String(8), default="")
    fund_type: Mapped[str] = mapped_column(String(32), default="unknown")
    note: Mapped[str] = mapped_column(Text, default="")
    planned_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    nav_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_source: Mapped[str] = mapped_column(String(80), default="待刷新")
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NavPoint(Base):
    __tablename__ = "v1_nav_points"
    __table_args__ = (UniqueConstraint("candidate_id", "nav_date", name="uq_v1_nav"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("v1_candidates.id", ondelete="CASCADE"))
    nav_date: Mapped[date] = mapped_column(Date)
    nav: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(80))
    candidate: Mapped[Candidate] = relationship()


class Holding(Base):
    __tablename__ = "v1_holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(6), index=True)
    fund_name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    holding_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(80), default="人工录入")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    __tablename__ = "v1_transactions"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_v1_transaction_fp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_code: Mapped[str] = mapped_column(String(6), index=True)
    fund_name: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(24))
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(80), default="人工录入")
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportBatch(Base):
    __tablename__ = "v1_import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(240))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    image_path: Mapped[str] = mapped_column(Text)
    page_type: Mapped[str] = mapped_column(String(40), default="unknown")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="needs_review")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list["ImportItem"]] = relationship(
        cascade="all, delete-orphan", order_by="ImportItem.id"
    )


class ImportItem(Base):
    __tablename__ = "v1_import_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("v1_import_batches.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), default="candidate")
    fund_code: Mapped[str] = mapped_column(String(6), default="")
    fund_name: Mapped[str] = mapped_column(String(200), default="")
    action: Mapped[str] = mapped_column(String(24), default="")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    issues: Mapped[str] = mapped_column(Text, default="")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class AnalysisReport(Base):
    __tablename__ = "v1_analysis_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("v1_candidates.id", ondelete="CASCADE"))
    horizon: Mapped[str] = mapped_column(String(16))
    result_json: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evidence(Base):
    __tablename__ = "v1_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("v1_candidates.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240))
    source_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[date] = mapped_column(Date)
    trust_level: Mapped[str] = mapped_column(String(16), default="B")
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TriggerRule(Base):
    __tablename__ = "v1_trigger_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("v1_candidates.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(48))
    operator: Mapped[str] = mapped_column(String(8))
    threshold: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_matched: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
