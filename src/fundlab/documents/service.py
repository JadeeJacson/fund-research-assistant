from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime

from fundlab.domain.enums import DocumentType, TrustLevel
from fundlab.domain.models import EvidenceItem, SourceDocument


def normalize_document_text(text: str) -> str:
    """移除多余空白，保留原始语义。外部文本仍会被视为不可信输入。"""

    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    cleaned = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n"))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if not cleaned:
        raise ValueError("文档内容不能为空")
    return cleaned


def create_document_and_evidence(
    *,
    subject_id: str,
    text: str,
    source_name: str,
    published_at: datetime,
    source_url: str | None = None,
    document_type: DocumentType = DocumentType.USER_NOTE,
    trust_level: TrustLevel = TrustLevel.OTHER,
    max_quote_chars: int = 700,
) -> tuple[SourceDocument, list[EvidenceItem]]:
    normalized = normalize_document_text(text)
    content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    document_id = f"doc-{content_hash[:20]}"
    document = SourceDocument(
        document_id=document_id,
        document_type=document_type,
        subject_ids=[subject_id],
        source_name=source_name,
        source_url=source_url,
        published_at=published_at,
        content_hash=content_hash,
        normalized_text=normalized,
        trust_level=trust_level,
    )

    # 按自然段生成证据单元，过长段落再切分。模型只能引用这些 evidence_id。
    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    quotes: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_quote_chars:
            quotes.append(paragraph)
        else:
            quotes.extend(
                paragraph[index : index + max_quote_chars]
                for index in range(0, len(paragraph), max_quote_chars)
            )
    evidence = [
        EvidenceItem(
            evidence_id=f"ev-{uuid.uuid5(uuid.NAMESPACE_URL, document_id + str(index)).hex[:20]}",
            document_id=document_id,
            subject_id=subject_id,
            quote=quote,
            published_at=published_at,
            source_name=source_name,
            source_url=source_url,
            trust_level=trust_level,
        )
        for index, quote in enumerate(quotes)
    ]
    return document, evidence
