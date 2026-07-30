from datetime import date, timedelta

from app.analytics import calculate_metrics
from app.decision import DecisionContext, build_decision


def test_metrics_and_long_horizon_decision():
    start = date(2025, 1, 1)
    points = [(start + timedelta(days=index), 1 + index / 2000) for index in range(400)]
    metrics = calculate_metrics(points)
    result = build_decision(
        metrics,
        DecisionContext(
            fund_name="沪深300指数基金A",
            fund_type="index",
            horizon="long",
            current_weight=0,
            data_source="AKShare（公开数据）",
            risk_tolerance=0.10,
        ),
    )
    assert metrics.observations == 400
    assert metrics.max_drawdown == 0
    assert result["state"] == "建仓候选"
    assert result["target_weight"][1] > 0


def test_unsupported_fund_is_gated():
    start = date(2025, 1, 1)
    metrics = calculate_metrics(
        [(start + timedelta(days=index), 1 + index / 2000) for index in range(200)]
    )
    result = build_decision(
        metrics,
        DecisionContext(
            fund_name="海外科技QDII",
            fund_type="unsupported",
            horizon="short",
            current_weight=0,
            data_source="公开数据",
            risk_tolerance=0.10,
        ),
    )
    assert result["state"] == "暂不支持完整评价"
