from __future__ import annotations

from datetime import date

from fundlab.ai.orchestrator import EvidenceAnalysisOrchestrator
from fundlab.analytics import compute_metrics
from fundlab.config import Settings
from fundlab.domain.models import FundAnalysisReport
from fundlab.domain.protocols import FundDataProvider
from fundlab.pipeline import validate_nav_records
from fundlab.retrieval import DatabaseRetriever
from fundlab.rules import build_decision
from fundlab.storage import Database


class FundResearchService:
    """单基金研究用例，负责协调 Provider、缓存、分析、规则和 AI。"""

    def __init__(
        self,
        provider: FundDataProvider,
        database: Database,
        settings: Settings,
        ai_orchestrator: EvidenceAnalysisOrchestrator | None = None,
    ):
        self.provider = provider
        self.database = database
        self.settings = settings
        self.ai_orchestrator = ai_orchestrator

    def analyze(
        self,
        fund_code: str,
        *,
        refresh: bool = True,
        include_ai: bool = False,
        as_of_date: date | None = None,
    ) -> FundAnalysisReport:
        code = fund_code.strip()
        profile = None
        nav_records = []
        provider_error: Exception | None = None
        if refresh:
            try:
                profile = self.provider.get_fund_profile(code)
                nav_records = self.provider.get_nav_history(code)
                self.database.upsert_fund(profile)
                self.database.upsert_nav(nav_records)
            except Exception as exc:
                provider_error = exc
                self.database.add_quality_event(
                    "provider_failure",
                    "warning",
                    str(exc),
                    subject_id=f"fund:{code}",
                    provider=self.provider.name,
                )

        if profile is None:
            profile = self.database.get_fund_by_code(code)
        if profile is None:
            raise RuntimeError(
                f"无法获取基金 {code}，且本地没有缓存"
                + (f"：{provider_error}" if provider_error else "")
            )
        if not nav_records:
            nav_records = self.database.load_nav(profile.fund_id)

        validation = validate_nav_records(nav_records, today=as_of_date)
        if not validation.is_valid:
            raise RuntimeError("；".join(validation.errors))
        metrics = compute_metrics(
            validation.records, annual_risk_free_rate=self.settings.risk_free_rate
        )
        decision = build_decision(
            profile,
            metrics,
            risk_tolerance=self.settings.risk_tolerance,
            validation_warnings=validation.warnings,
            today=as_of_date,
        )

        ai_analysis = None
        effective_date = as_of_date or metrics.end_date
        if include_ai and self.ai_orchestrator is not None:
            evidence = DatabaseRetriever(self.database).retrieve_evidence(
                profile.fund_id, as_of_date=effective_date
            )
            ai_analysis = self.ai_orchestrator.analyze(
                subject_id=profile.fund_id,
                as_of_date=effective_date,
                evidence=evidence,
                metrics=metrics,
            )

        report = FundAnalysisReport(
            fund=profile,
            metrics=metrics,
            decision=decision,
            ai_analysis=ai_analysis,
        )
        self.database.save_report(report)
        return report
