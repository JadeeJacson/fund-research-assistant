from __future__ import annotations

import unittest
from datetime import date

from fundlab.analytics.portfolio import calculate_positions, calculate_xirr
from fundlab.domain.enums import TransactionAction
from fundlab.domain.models import TransactionRecord


class PortfolioTests(unittest.TestCase):
    def test_positions(self) -> None:
        transactions = [
            TransactionRecord(
                account="a",
                fund_code="000001",
                share_class="A",
                trade_date=date(2026, 1, 1),
                action=TransactionAction.BUY,
                shares=100,
                amount=100,
                source="test",
            ),
            TransactionRecord(
                account="a",
                fund_code="000001",
                share_class="A",
                trade_date=date(2026, 2, 1),
                action=TransactionAction.SELL,
                shares=20,
                amount=25,
                source="test",
            ),
        ]
        self.assertEqual(calculate_positions(transactions)["000001:A"], 80)

    def test_xirr(self) -> None:
        value = calculate_xirr([(date(2025, 1, 1), -1000), (date(2026, 1, 1), 1100)])
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, 0.10, places=3)


if __name__ == "__main__":
    unittest.main()
