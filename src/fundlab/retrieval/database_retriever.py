from __future__ import annotations

from datetime import UTC, date, datetime, time

from fundlab.domain.models import EvidenceItem
from fundlab.storage import Database


class DatabaseRetriever:
    """基于结构化元数据的第一版检索器。

    第一版不引入向量数据库。未来可以新增实现，但调用方不需要变化。
    """

    def __init__(self, database: Database):
        self.database = database

    def retrieve_evidence(
        self, subject_id: str, *, as_of_date: date, limit: int = 20
    ) -> list[EvidenceItem]:
        cutoff = datetime.combine(as_of_date, time.max, tzinfo=UTC)
        return [
            item
            for item in self.database.list_evidence(subject_id, limit=limit * 2)
            if item.published_at <= cutoff
        ][:limit]
