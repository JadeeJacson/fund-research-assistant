from __future__ import annotations

from collections import defaultdict
from datetime import date

from scipy.optimize import brentq

from fundlab.domain.enums import TransactionAction
from fundlab.domain.models import TransactionRecord


def calculate_positions(transactions: list[TransactionRecord]) -> dict[str, float]:
    positions: dict[str, float] = defaultdict(float)
    for item in sorted(transactions, key=lambda value: value.trade_date):
        key = f"{item.fund_code}:{item.share_class}"
        if item.action in {
            TransactionAction.BUY,
            TransactionAction.DIVIDEND_REINVEST,
            TransactionAction.TRANSFER_IN,
        }:
            positions[key] += item.shares
        elif item.action in {TransactionAction.SELL, TransactionAction.TRANSFER_OUT}:
            positions[key] -= item.shares
        elif item.action == TransactionAction.ADJUSTMENT:
            positions[key] += item.shares
    return dict(positions)


def calculate_xirr(cash_flows: list[tuple[date, float]]) -> float | None:
    """按实际日期计算 XIRR。投入应为负数，回款和期末价值应为正数。"""

    if (
        len(cash_flows) < 2
        or not any(v < 0 for _, v in cash_flows)
        or not any(v > 0 for _, v in cash_flows)
    ):
        return None
    ordered = sorted(cash_flows)
    start = ordered[0][0]

    def npv(rate: float) -> float:
        return sum(value / (1 + rate) ** ((day - start).days / 365.25) for day, value in ordered)

    try:
        return float(brentq(npv, -0.9999, 100.0, maxiter=200))
    except ValueError:
        return None
