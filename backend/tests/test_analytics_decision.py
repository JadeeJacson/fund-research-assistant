from datetime import date, timedelta
from pathlib import Path

from app.analytics import Metrics, calculate_metrics, calculate_window_metrics
from app.config import RuleConfig
from app.decision import (
    bucket_allocation,
    compare_alternative,
    evaluate_fund,
    select_headlines,
)
from app.services import trading_days_between

RULES = RuleConfig.load(Path(__file__).parents[2] / "config" / "decision_rules.yaml").values


def metric(*, sharpe: float = 0.5, drawdown: float = -0.03) -> Metrics:
    return Metrics(date.today(), 251, 0.1, 0.01, 0.03, 0.1, 0.1, 0.2, drawdown, sharpe, 2.0)


def test_rule_config_and_bucket_invariants():
    assert sum(item["mid"] for item in RULES["buckets"].values()) == 1
    assert RULES["quality"]["min_observations"] == 50
    assert RULES["buckets"]["satellite"]["horizon_days"] + 1 >= RULES["quality"]["min_observations"]
    summary = bucket_allocation(
        [
            {"amount": 400, "bucket": "defense"},
            {"amount": 350, "bucket": "core"},
            {"amount": 250, "bucket": "satellite"},
        ],
        RULES,
    )
    assert all(item["in_band"] for item in summary.values())
    assert summary["defense"]["weight"] == 0.4


def test_data_gate_and_verified_hard_risk_take_priority():
    fund = {"code": "000001", "name": "测试主动基金", "fund_type": "mixed"}
    blocked = evaluate_fund(
        fund=fund, bucket="core", metrics=None, evidences=[], rules=RULES, data_quality="blocked"
    )
    assert blocked[0].reason_type == "data_quality"
    assert blocked[0].proposed_action == "observe"

    detailed = evaluate_fund(
        fund=fund,
        bucket="core",
        metrics=metric(),
        evidences=[],
        rules=RULES,
        data_quality="blocked",
        data_quality_detail="累计净值观察值不足：实际 42 个，至少需要 50 个。",
    )
    assert "实际 42 个" in detailed[0].detail
    assert detailed[0].metrics["required_observations"] == 50

    hard = evaluate_fund(
        fund={**fund, "peer_percentile": 90, "laggard_trading_days": 0},
        bucket="core",
        metrics=metric(),
        evidences=[
            {
                "id": 8,
                "title": "基金合同终止公告",
                "event_type": "contract_termination",
                "source_level": "S",
                "evidence_kind": "announcement",
                "verified": True,
                "severity": "critical",
            }
        ],
        rules=RULES,
        data_quality="ready",
    )
    assert hard[0].reason_type == "hard_risk"
    assert hard[0].proposed_action == "exit_review"


def test_quality_trigger_requires_persistent_bottom_third_and_second_dimension():
    fund = {
        "code": "000001",
        "name": "测试主动基金",
        "fund_type": "mixed",
        "peer_percentile": 20,
        "laggard_trading_days": 20,
        "redemption_status": "开放赎回",
    }
    assert evaluate_fund(
        fund=fund,
        bucket="core",
        metrics=metric(sharpe=0.4),
        evidences=[],
        rules=RULES,
        data_quality="ready",
    ) == []
    findings = evaluate_fund(
        fund=fund,
        bucket="core",
        metrics=metric(sharpe=-0.2),
        evidences=[],
        rules=RULES,
        data_quality="ready",
    )
    assert findings[0].reason_type == "quality_deterioration"
    assert findings[0].metrics["laggard_trading_days"] == 20


def test_total_return_metrics_and_alternative_have_no_composite_score():
    start = date(2025, 1, 1)
    points = [(start + timedelta(days=index), 1 + index / 1000) for index in range(400)]
    metrics = calculate_metrics(points)
    assert metrics.observations == 400
    assert metrics.max_drawdown == 0
    assert calculate_window_metrics(points, 55).observations == 56

    improvements, counterpoints = compare_alternative(
        {"peer_percentile": 20, "expense_ratio": 0.008},
        {"peer_percentile": 40, "expense_ratio": 0.005, "quality_status": "ready"},
        metric(sharpe=0.5, drawdown=-0.08),
        metric(sharpe=0.7, drawdown=-0.04),
        "core",
        RULES,
    )
    assert len(improvements) >= 2
    assert not counterpoints


def test_headlines_are_bounded_and_deduplicated():
    findings = evaluate_fund(
        fund={"code": "000001", "name": "基金一", "fund_type": "mixed"},
        bucket="core",
        metrics=None,
        evidences=[],
        rules=RULES,
        data_quality="blocked",
    )
    headlines = select_headlines(findings * 5, [], 3)
    assert len(headlines) == 1
    assert headlines[0]["title"].endswith("数据不足")


def test_cooldowns_count_trading_days_not_clicks():
    monday = date(2026, 8, 24)
    assert trading_days_between(monday, monday) == 0
    assert trading_days_between(monday, monday + timedelta(days=4)) == 4
    assert trading_days_between(monday, monday + timedelta(days=7)) == 5
