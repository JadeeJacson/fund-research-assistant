from __future__ import annotations

import unittest
from datetime import date

from fundlab.analytics import compute_metrics
from fundlab.domain.enums import AnalysisState, FundType
from fundlab.domain.models import FundProfile
from fundlab.rules import build_decision
from tests.helpers import make_nav_records


class RuleTests(unittest.TestCase):
    def test_drawdown_over_budget_reduces_fit(self) -> None:
        metrics = compute_metrics(make_nav_records(drawdown_size=0.30))
        fund = FundProfile(
            fund_code="000001",
            share_class="A",
            fund_name="测试指数基金A",
            fund_type=FundType.INDEX,
            source="test",
        )
        decision = build_decision(
            fund,
            metrics,
            risk_tolerance=0.10,
            today=date(2025, 5, 14),
        )
        self.assertEqual(decision.state, AnalysisState.NOT_SUITABLE)
        self.assertIn("RISK_DRAWDOWN_OVER_BUDGET", decision.triggered_rules)

    def test_short_history_is_insufficient(self) -> None:
        metrics = compute_metrics(make_nav_records(days=100))
        fund = FundProfile(fund_code="000001", fund_name="测试基金", source="test")
        decision = build_decision(fund, metrics, risk_tolerance=0.10)
        self.assertEqual(decision.state, AnalysisState.INSUFFICIENT_DATA)


if __name__ == "__main__":
    unittest.main()
