from __future__ import annotations

from enum import StrEnum


class FundType(StrEnum):
    INDEX = "index"
    ACTIVE_EQUITY = "active_equity"
    BOND = "bond"
    MONEY = "money"
    QDII = "qdii"
    COMMODITY = "commodity"
    FOF = "fof"
    REIT = "reit"
    UNKNOWN = "unknown"


class DataQuality(StrEnum):
    OK = "ok"
    STALE = "stale"
    MISSING = "missing"
    CONFLICT = "conflict"
    INVALID = "invalid"


class AnalysisState(StrEnum):
    INSUFFICIENT_DATA = "数据不足"
    NOT_SUITABLE = "不适配"
    WATCH = "继续观察"
    REBALANCE_CANDIDATE = "再平衡候选"
    HOLD_REVIEW = "持有复核"


class Direction(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNCERTAIN = "uncertain"


class ImpactHorizon(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    UNKNOWN = "unknown"


class DocumentType(StrEnum):
    ANNOUNCEMENT = "announcement"
    PERIODIC_REPORT = "periodic_report"
    NEWS = "news"
    POLICY = "policy"
    USER_NOTE = "user_note"


class TrustLevel(StrEnum):
    OFFICIAL = "official"
    PRIMARY = "primary"
    RELIABLE_MEDIA = "reliable_media"
    OTHER = "other"


class TransactionAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND_CASH = "dividend_cash"
    DIVIDEND_REINVEST = "dividend_reinvest"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT = "adjustment"
