from __future__ import annotations

import unittest
from datetime import UTC, datetime

from fundlab.documents import create_document_and_evidence, normalize_document_text


class DocumentTests(unittest.TestCase):
    def test_normalize_whitespace(self) -> None:
        self.assertEqual(normalize_document_text("  第一段  \n\n\n 第二段 "), "第一段\n\n第二段")

    def test_evidence_is_stable_and_bounded(self) -> None:
        document, evidence = create_document_and_evidence(
            subject_id="000001:A",
            text="测试段落" * 300,
            source_name="test",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            max_quote_chars=100,
        )
        self.assertTrue(document.document_id.startswith("doc-"))
        self.assertGreater(len(evidence), 1)
        self.assertTrue(all(len(item.quote) <= 100 for item in evidence))


if __name__ == "__main__":
    unittest.main()
