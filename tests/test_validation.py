from __future__ import annotations

import unittest
from datetime import date

from fundlab.domain.models import NavRecord
from fundlab.pipeline import validate_nav_records


class ValidationTests(unittest.TestCase):
    def test_empty_records_are_invalid(self) -> None:
        result = validate_nav_records([])
        self.assertFalse(result.is_valid)

    def test_conflicting_same_day_nav_is_error(self) -> None:
        records = [
            NavRecord(fund_id="x", nav_date=date(2026, 1, 1), unit_nav=1, source="a"),
            NavRecord(fund_id="x", nav_date=date(2026, 1, 1), unit_nav=2, source="b"),
        ]
        result = validate_nav_records(records, today=date(2026, 1, 2))
        self.assertTrue(result.errors)

    def test_large_jump_is_warning(self) -> None:
        records = [
            NavRecord(fund_id="x", nav_date=date(2026, 1, 1), unit_nav=1, source="a"),
            NavRecord(fund_id="x", nav_date=date(2026, 1, 2), unit_nav=1.3, source="a"),
        ]
        result = validate_nav_records(records, today=date(2026, 1, 2))
        self.assertTrue(any("单日净值" in item for item in result.warnings))


if __name__ == "__main__":
    unittest.main()
