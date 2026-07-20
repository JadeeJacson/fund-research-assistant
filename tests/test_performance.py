from __future__ import annotations

import unittest

from fundlab.analytics import compute_metrics
from tests.helpers import make_nav_records


class PerformanceTests(unittest.TestCase):
    def test_compute_metrics_has_negative_drawdown(self) -> None:
        metrics = compute_metrics(make_nav_records())
        self.assertEqual(metrics.observations, 500)
        self.assertLess(metrics.max_drawdown, -0.10)
        self.assertGreater(metrics.annualized_volatility, 0)
        self.assertIsNotNone(metrics.sharpe_ratio)

    def test_monotonic_series_has_zero_drawdown(self) -> None:
        metrics = compute_metrics(make_nav_records(drawdown_at=None))
        self.assertAlmostEqual(metrics.max_drawdown, 0.0)
        self.assertIsNone(metrics.calmar_ratio)

    def test_requires_two_observations(self) -> None:
        with self.assertRaises(ValueError):
            compute_metrics(make_nav_records(days=1))


if __name__ == "__main__":
    unittest.main()
