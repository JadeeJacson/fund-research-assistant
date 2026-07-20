from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from fundlab.ai import EvidenceAnalysisOrchestrator
from fundlab.ai.providers import MockLLMProvider
from fundlab.ai.safety import AIValidationError, validate_ai_analysis
from fundlab.config import Settings
from fundlab.domain.enums import Direction, ImpactHorizon, TrustLevel
from fundlab.domain.models import AIAnalysis, AIEvent, EvidenceItem
from fundlab.storage import Database


class AITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.settings = Settings(
            project_root=Path(__file__).resolve().parents[1],
            data_dir=root / "data",
            database_path=root / "test.sqlite3",
        )
        self.database = Database(self.settings.database_path)
        self.database.initialize()
        self.evidence = EvidenceItem(
            evidence_id="ev-1",
            document_id="doc-1",
            subject_id="000001:A",
            quote="基金经理发生变更。",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            source_name="官方公告",
            trust_level=TrustLevel.OFFICIAL,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_mock_orchestrator_and_audit(self) -> None:
        orchestrator = EvidenceAnalysisOrchestrator(MockLLMProvider(), self.database, self.settings)
        result = orchestrator.analyze(
            subject_id="000001:A",
            as_of_date=date(2026, 1, 2),
            evidence=[self.evidence],
        )
        self.assertEqual(result.subject_id, "000001:A")
        self.assertEqual(len(self.database.list_ai_runs()), 1)

    def test_unknown_evidence_is_rejected(self) -> None:
        analysis = AIAnalysis(
            subject_id="000001:A",
            as_of_date=date(2026, 1, 2),
            summary="test",
            events=[
                AIEvent(
                    event_type="x",
                    direction=Direction.UNCERTAIN,
                    impact_horizon=ImpactHorizon.UNKNOWN,
                    confidence=0.2,
                    evidence_ids=["ev-does-not-exist"],
                    reasoning_summary="test",
                )
            ],
        )
        with self.assertRaises(AIValidationError):
            validate_ai_analysis(
                analysis,
                [self.evidence],
                expected_subject_id="000001:A",
                as_of_date=date(2026, 1, 2),
            )


if __name__ == "__main__":
    unittest.main()
