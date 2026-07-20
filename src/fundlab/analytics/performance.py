from __future__ import annotations

import math

import numpy as np
import pandas as pd

from fundlab.domain.models import MetricSet, NavRecord

TRADING_DAYS = 252


def nav_series(records: list[NavRecord]) -> pd.Series:
    if len(records) < 2:
        raise ValueError("至少需要两个净值观察值")
    values = {pd.Timestamp(record.nav_date): record.return_nav for record in records}
    series = pd.Series(values, dtype=float).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    if (series <= 0).any() or series.isna().any():
        raise ValueError("净值必须为正数且不能包含空值")
    return series


def _finite_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def compute_metrics(records: list[NavRecord], annual_risk_free_rate: float = 0.0) -> MetricSet:
    series = nav_series(records)
    returns = series.pct_change().dropna()
    calendar_days = max((series.index[-1] - series.index[0]).days, 1)
    total_return = float(series.iloc[-1] / series.iloc[0] - 1)
    annualized_return = float((1 + total_return) ** (365.25 / calendar_days) - 1)
    annualized_volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))

    rolling_peak = series.cummax()
    drawdowns = series / rolling_peak - 1
    trough_date = drawdowns.idxmin()
    max_drawdown = float(drawdowns.loc[trough_date])
    peak_date = series.loc[:trough_date].idxmax()
    recovery_candidates = series.loc[trough_date:][
        series.loc[trough_date:] >= series.loc[peak_date]
    ]
    recovery_date = recovery_candidates.index[0] if not recovery_candidates.empty else None
    drawdown_end = recovery_date or series.index[-1]
    max_drawdown_days = int((drawdown_end - peak_date).days)
    recovery_days = int((recovery_date - trough_date).days) if recovery_date is not None else None

    sharpe = None
    if annualized_volatility > 0:
        sharpe = (annualized_return - annual_risk_free_rate) / annualized_volatility

    downside = returns[returns < 0]
    downside_deviation = (
        float(downside.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(downside) > 1 else 0.0
    )
    sortino = (
        (annualized_return - annual_risk_free_rate) / downside_deviation
        if downside_deviation > 0
        else None
    )
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else None

    return MetricSet(
        observations=len(series),
        start_date=series.index[0].date(),
        end_date=series.index[-1].date(),
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        max_drawdown=max_drawdown,
        max_drawdown_days=max_drawdown_days,
        recovery_days=recovery_days,
        sharpe_ratio=_finite_or_none(sharpe) if sharpe is not None else None,
        sortino_ratio=_finite_or_none(sortino) if sortino is not None else None,
        calmar_ratio=_finite_or_none(calmar) if calmar is not None else None,
    )
