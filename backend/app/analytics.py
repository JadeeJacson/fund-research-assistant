from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Metrics:
    as_of_date: date
    observations: int
    total_return: float | None
    return_1m: float | None
    return_3m: float | None
    return_1y: float | None
    annualized_return: float | None
    volatility: float | None
    max_drawdown: float | None

    def as_dict(self) -> dict:
        values = asdict(self)
        values["as_of_date"] = self.as_of_date.isoformat()
        return values


def _period_return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] <= 0:
        return None
    return values[-1] / values[-periods - 1] - 1


def calculate_metrics(points: list[tuple[date, float]]) -> Metrics:
    if not points:
        raise ValueError("缺少净值数据")
    clean = sorted((day, float(value)) for day, value in points if value and value > 0)
    if not clean:
        raise ValueError("净值数据无有效正数")
    values = [value for _, value in clean]
    daily = [values[index] / values[index - 1] - 1 for index in range(1, len(values))]
    total_return = values[-1] / values[0] - 1 if len(values) > 1 else None
    elapsed_days = max((clean[-1][0] - clean[0][0]).days, 1)
    annualized = (
        (values[-1] / values[0]) ** (365 / elapsed_days) - 1 if len(values) > 1 else None
    )
    if len(daily) > 1:
        mean = sum(daily) / len(daily)
        variance = sum((item - mean) ** 2 for item in daily) / (len(daily) - 1)
        volatility = math.sqrt(variance) * math.sqrt(252)
    else:
        volatility = None
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
    return Metrics(
        as_of_date=clean[-1][0],
        observations=len(clean),
        total_return=total_return,
        return_1m=_period_return(values, 21),
        return_3m=_period_return(values, 63),
        return_1y=_period_return(values, 252),
        annualized_return=annualized,
        volatility=volatility,
        max_drawdown=max_drawdown,
    )
