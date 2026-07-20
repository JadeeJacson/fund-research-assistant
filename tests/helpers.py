from __future__ import annotations

from datetime import date, timedelta

from fundlab.domain.models import NavRecord


def make_nav_records(
    days: int = 500,
    *,
    start: date = date(2024, 1, 1),
    daily_growth: float = 0.0005,
    drawdown_at: int | None = 250,
    drawdown_size: float = 0.12,
) -> list[NavRecord]:
    value = 1.0
    records: list[NavRecord] = []
    for index in range(days):
        value *= 1 + daily_growth
        if drawdown_at is not None and index == drawdown_at:
            value *= 1 - drawdown_size
        records.append(
            NavRecord(
                fund_id="000001:A",
                nav_date=start + timedelta(days=index),
                unit_nav=value,
                adjusted_nav=value,
                source="test",
            )
        )
    return records
