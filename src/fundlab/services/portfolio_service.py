from __future__ import annotations

from pathlib import Path

import pandas as pd

from fundlab.analytics.portfolio import calculate_positions
from fundlab.domain.models import TransactionRecord
from fundlab.storage import Database


class PortfolioService:
    REQUIRED_COLUMNS = {
        "account",
        "fund_code",
        "share_class",
        "trade_date",
        "action",
        "amount",
        "shares",
        "nav",
        "fee",
        "dividend",
        "source",
    }

    def __init__(self, database: Database):
        self.database = database

    def import_csv(self, path_or_buffer: Path | str | object) -> tuple[int, int]:
        frame = pd.read_csv(path_or_buffer, dtype={"fund_code": str})
        missing = self.REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            raise ValueError(f"交易 CSV 缺少字段：{sorted(missing)}")
        inserted = 0
        duplicates = 0
        for row in frame.to_dict(orient="records"):
            values = {key: (None if pd.isna(value) else value) for key, value in row.items()}
            values["fund_code"] = str(values["fund_code"]).zfill(6)
            transaction = TransactionRecord.model_validate(values)
            if self.database.insert_transaction(transaction):
                inserted += 1
            else:
                duplicates += 1
        return inserted, duplicates

    def positions(self) -> dict[str, float]:
        return calculate_positions(self.database.list_transactions())
