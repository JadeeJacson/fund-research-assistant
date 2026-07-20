from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from fundlab.domain.models import FundProfile, NavRecord

from .classification import classify_fund_name, infer_share_class


class ManualCsvProvider:
    """本地 CSV 备用 Provider，适合上游接口失效或导入自有净值数据。"""

    name = "manual_csv"

    def __init__(self, nav_csv: Path | str, fund_name: str, fund_code: str):
        self.nav_csv = Path(nav_csv)
        self.fund_name = fund_name
        self.fund_code = fund_code

    def health_check(self) -> tuple[bool, str]:
        return self.nav_csv.exists(), str(self.nav_csv)

    def get_fund_profile(self, fund_code: str) -> FundProfile:
        if fund_code != self.fund_code:
            raise ValueError(f"本文件只包含基金 {self.fund_code}")
        return FundProfile(
            fund_code=fund_code,
            share_class=infer_share_class(self.fund_name),
            fund_name=self.fund_name,
            fund_type=classify_fund_name(self.fund_name),
            source=self.name,
        )

    def get_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[NavRecord]:
        profile = self.get_fund_profile(fund_code)
        frame = pd.read_csv(self.nav_csv)
        required = {"nav_date", "unit_nav"}
        if not required.issubset(frame.columns):
            raise ValueError(f"净值 CSV 必须包含字段：{sorted(required)}")
        fetched_at = datetime.now(UTC)
        records: list[NavRecord] = []
        for row in frame.to_dict(orient="records"):
            nav_date = pd.to_datetime(row["nav_date"]).date()
            if start_date and nav_date < start_date:
                continue
            if end_date and nav_date > end_date:
                continue
            records.append(
                NavRecord(
                    fund_id=profile.fund_id,
                    nav_date=nav_date,
                    unit_nav=float(row["unit_nav"]),
                    accumulated_nav=self._optional_float(row.get("accumulated_nav")),
                    adjusted_nav=self._optional_float(row.get("adjusted_nav")),
                    source=self.name,
                    fetched_at=fetched_at,
                )
            )
        return sorted(records, key=lambda item: item.nav_date)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None or pd.isna(value) or value == "":
            return None
        return float(value)
