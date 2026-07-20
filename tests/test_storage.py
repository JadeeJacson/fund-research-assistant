from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fundlab.documents import create_document_and_evidence
from fundlab.domain.enums import TrustLevel
from fundlab.domain.models import FundProfile
from fundlab.storage import Database


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary.name) / "test.sqlite3")
        self.database.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_round_trip_fund(self) -> None:
        fund = FundProfile(
            fund_code="000001", share_class="A", fund_name="测试基金A", source="test"
        )
        self.database.upsert_fund(fund)
        loaded = self.database.get_fund(fund.fund_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.fund_name, fund.fund_name)

    def test_document_and_evidence(self) -> None:
        document, evidence = create_document_and_evidence(
            subject_id="000001:A",
            text="基金管理人发布公告。\n\n基金经理发生变更。",
            source_name="测试官方来源",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            trust_level=TrustLevel.OFFICIAL,
        )
        self.database.add_document(document)
        for item in evidence:
            self.database.add_evidence(item)
        loaded = self.database.list_evidence("000001:A")
        self.assertEqual(len(loaded), 2)


if __name__ == "__main__":
    unittest.main()
