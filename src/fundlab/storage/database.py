from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fundlab.domain.models import (
    EvidenceItem,
    FundAnalysisReport,
    FundProfile,
    NavRecord,
    SourceDocument,
    TransactionRecord,
)

from .schema import SCHEMA_SQL, SCHEMA_VERSION


class Database:
    """轻量 SQLite 存储。

    这是单用户本地应用；如果未来改为多用户云服务，应替换为正式数据库和迁移工具。
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
            )
            # FTS5 并非所有 SQLite 构建都启用，因此失败时保留 LIKE 检索降级路径。
            with suppress(sqlite3.OperationalError):
                connection.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(document_id, normalized_text)"
                )

    def upsert_fund(self, fund: FundProfile) -> None:
        values = fund.model_dump(mode="json")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO funds(
                    fund_id, fund_code, share_class, fund_name, fund_type,
                    benchmark_code, manager_name, inception_date, management_fee,
                    custodian_fee, source, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fund_id) DO UPDATE SET
                    fund_name=excluded.fund_name, fund_type=excluded.fund_type,
                    benchmark_code=excluded.benchmark_code, manager_name=excluded.manager_name,
                    inception_date=excluded.inception_date, management_fee=excluded.management_fee,
                    custodian_fee=excluded.custodian_fee, source=excluded.source,
                    fetched_at=excluded.fetched_at
                """,
                (
                    fund.fund_id,
                    values["fund_code"],
                    values["share_class"],
                    values["fund_name"],
                    values["fund_type"],
                    values["benchmark_code"],
                    values["manager_name"],
                    values["inception_date"],
                    values["management_fee"],
                    values["custodian_fee"],
                    values["source"],
                    values["fetched_at"],
                ),
            )

    def get_fund(self, fund_id: str) -> FundProfile | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM funds WHERE fund_id=?", (fund_id,)).fetchone()
        if row is None:
            return None
        values = dict(row)
        values.pop("fund_id", None)
        return FundProfile.model_validate(values)

    def get_fund_by_code(self, fund_code: str) -> FundProfile | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM funds WHERE fund_code=? ORDER BY fetched_at DESC LIMIT 1",
                (fund_code,),
            ).fetchone()
        if row is None:
            return None
        values = dict(row)
        values.pop("fund_id", None)
        return FundProfile.model_validate(values)

    def upsert_nav(self, records: list[NavRecord]) -> int:
        if not records:
            return 0
        rows = []
        for record in records:
            values = record.model_dump(mode="json")
            rows.append(
                (
                    values["fund_id"],
                    values["nav_date"],
                    values["unit_nav"],
                    values["accumulated_nav"],
                    values["adjusted_nav"],
                    values["source"],
                    values["fetched_at"],
                    values["quality_status"],
                )
            )
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO fund_nav(
                    fund_id, nav_date, unit_nav, accumulated_nav, adjusted_nav,
                    source, fetched_at, quality_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fund_id, nav_date, source) DO UPDATE SET
                    unit_nav=excluded.unit_nav,
                    accumulated_nav=excluded.accumulated_nav,
                    adjusted_nav=excluded.adjusted_nav,
                    fetched_at=excluded.fetched_at,
                    quality_status=excluded.quality_status
                """,
                rows,
            )
        return len(rows)

    def load_nav(self, fund_id: str) -> list[NavRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM fund_nav WHERE fund_id=? ORDER BY nav_date", (fund_id,)
            ).fetchall()
        return [NavRecord.model_validate(dict(row)) for row in rows]

    def insert_transaction(self, transaction: TransactionRecord) -> bool:
        payload = transaction.model_dump(mode="json")
        payload_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        transaction_id = transaction.external_id or str(uuid.uuid4())
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO transactions(
                        transaction_id, external_id, account, fund_code, share_class,
                        trade_date, action, amount, shares, nav, fee, dividend, source,
                        payload_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transaction_id,
                        payload["external_id"],
                        payload["account"],
                        payload["fund_code"],
                        payload["share_class"],
                        payload["trade_date"],
                        payload["action"],
                        payload["amount"],
                        payload["shares"],
                        payload["nav"],
                        payload["fee"],
                        payload["dividend"],
                        payload["source"],
                        payload_hash,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def list_transactions(self) -> list[TransactionRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT account, fund_code, share_class, trade_date, action, amount,
                       shares, nav, fee, dividend, source, external_id
                FROM transactions ORDER BY trade_date, transaction_id
                """
            ).fetchall()
        return [TransactionRecord.model_validate(dict(row)) for row in rows]

    def add_document(self, document: SourceDocument) -> None:
        values = document.model_dump(mode="json")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO documents(
                    document_id, document_type, subject_ids_json, source_name, source_url,
                    published_at, effective_at, fetched_at, content_hash, normalized_text,
                    trust_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    subject_ids_json=excluded.subject_ids_json,
                    normalized_text=excluded.normalized_text,
                    fetched_at=excluded.fetched_at
                """,
                (
                    values["document_id"],
                    values["document_type"],
                    json.dumps(values["subject_ids"], ensure_ascii=False),
                    values["source_name"],
                    values["source_url"],
                    values["published_at"],
                    values["effective_at"],
                    values["fetched_at"],
                    values["content_hash"],
                    values["normalized_text"],
                    values["trust_level"],
                ),
            )
            try:
                connection.execute(
                    "DELETE FROM documents_fts WHERE document_id=?", (document.document_id,)
                )
                connection.execute(
                    "INSERT INTO documents_fts(document_id, normalized_text) VALUES (?, ?)",
                    (document.document_id, document.normalized_text),
                )
            except sqlite3.OperationalError:
                pass

    def add_evidence(self, evidence: EvidenceItem) -> None:
        values = evidence.model_dump(mode="json")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evidence_items(
                    evidence_id, document_id, subject_id, quote, published_at,
                    source_name, source_url, trust_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(
                    values[key]
                    for key in (
                        "evidence_id",
                        "document_id",
                        "subject_id",
                        "quote",
                        "published_at",
                        "source_name",
                        "source_url",
                        "trust_level",
                    )
                ),
            )

    def list_evidence(self, subject_id: str, limit: int = 20) -> list[EvidenceItem]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM evidence_items WHERE subject_id=?
                ORDER BY published_at DESC LIMIT ?
                """,
                (subject_id, limit),
            ).fetchall()
        return [EvidenceItem.model_validate(dict(row)) for row in rows]

    def search_documents(
        self, subject_id: str, query: str = "", limit: int = 20
    ) -> list[dict[str, Any]]:
        like_subject = f'%"{subject_id}"%'
        like_query = f"%{query}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM documents
                WHERE subject_ids_json LIKE ? AND normalized_text LIKE ?
                ORDER BY published_at DESC LIMIT ?
                """,
                (like_subject, like_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_ai_run(self, values: dict[str, Any]) -> None:
        fields = (
            "run_id",
            "subject_id",
            "provider",
            "model",
            "prompt_name",
            "prompt_version",
            "input_hash",
            "output_schema_version",
            "started_at",
            "finished_at",
            "latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "estimated_cost_usd",
            "cached",
            "success",
            "output_json",
            "error",
        )
        normalized = {
            "finished_at": None,
            "latency_ms": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_cost_usd": 0.0,
            "cached": 0,
            "success": 0,
            "output_json": None,
            "error": None,
            **values,
        }
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO ai_runs({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                tuple(normalized.get(field) for field in fields),
            )

    def ai_spend_today(self, day_prefix: str) -> float:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(estimated_cost_usd), 0) AS total
                FROM ai_runs WHERE started_at LIKE ? AND success=1
                """,
                (f"{day_prefix}%",),
            ).fetchone()
        return float(row["total"] if row else 0.0)

    def add_quality_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        *,
        subject_id: str | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO data_quality_events(
                    event_id, subject_id, provider, event_type, severity, message,
                    details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    subject_id,
                    provider,
                    event_type,
                    severity,
                    message,
                    json.dumps(details or {}, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def list_quality_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM data_quality_events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_ai_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ai_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def save_report(self, report: FundAnalysisReport) -> str:
        report_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO analysis_reports(report_id, fund_id, generated_at, report_json) VALUES (?, ?, ?, ?)",
                (
                    report_id,
                    report.fund.fund_id,
                    report.generated_at.isoformat(),
                    report.model_dump_json(),
                ),
            )
        return report_id
