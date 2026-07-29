from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

KNOWN_FUNDS: dict[str, tuple[str, str, str]] = {
    "017470": ("嘉实上证科创板芯片ETF联接C", "index", "C"),
    "013308": ("易方达恒生科技ETF联接(QDII)A", "unsupported", "A"),
    "006328": ("易方达中概互联网ETF联接(QDII)C", "unsupported", "C"),
    "020972": ("易方达机器人ETF联接A", "index", "A"),
    "019028": ("广发添福30天持有期债券C", "bond", "C"),
    "011803": ("景顺长城宁景6个月持有期混合A", "active_equity", "A"),
    "006985": ("兴全恒裕债券A", "bond", "A"),
}


@dataclass(frozen=True, slots=True)
class FundData:
    fund_code: str
    fund_name: str
    fund_type: str
    share_class: str
    source: str
    nav_points: list[tuple[date, float]]


class MarketProvider(Protocol):
    name: str

    def load(self, fund_code: str) -> FundData: ...


def infer_type(name: str) -> str:
    upper = name.upper()
    if "QDII" in upper or "黄金" in name or "REIT" in upper or "FOF" in upper:
        return "unsupported"
    if "债券" in name or "纯债" in name:
        return "bond"
    if "ETF" in upper or "指数" in name:
        return "index"
    if "混合" in name or "股票" in name:
        return "active_equity"
    return "unknown"


def infer_share_class(name: str) -> str:
    tail = name.strip()[-1:].upper()
    return tail if tail in {"A", "B", "C", "D", "E", "I"} else ""


class DemoProvider:
    """离线可复现数据。只用于演示和测试，界面会明确标记。"""

    name = "离线演示数据"

    def load(self, fund_code: str) -> FundData:
        name, fund_type, share_class = KNOWN_FUNDS.get(
            fund_code, (f"待核验基金 {fund_code}", "unknown", "")
        )
        seed = int(fund_code[-3:]) or 1
        end = date.today()
        base = 1.0 + (seed % 70) / 100
        points: list[tuple[date, float]] = []
        for index in range(380):
            day = end - timedelta(days=379 - index)
            trend = index * ((seed % 9) - 2) / 150_000
            cycle = math.sin(index / 17 + seed) * (0.025 + (seed % 5) / 1000)
            shock = -0.08 if 210 <= index <= 225 and fund_type != "bond" else 0
            nav = max(0.2, base * (1 + trend + cycle + shock))
            points.append((day, round(nav, 4)))
        return FundData(
            fund_code=fund_code,
            fund_name=name,
            fund_type=fund_type,
            share_class=share_class,
            source=self.name,
            nav_points=points,
        )


class AkshareProvider:
    name = "AKShare（公开数据）"

    def load(self, fund_code: str) -> FundData:
        import akshare as ak

        names = ak.fund_name_em()
        row = names.loc[names["基金代码"].astype(str).str.zfill(6) == fund_code]
        fund_name = str(row.iloc[0]["基金简称"]) if not row.empty else f"基金 {fund_code}"
        history = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        date_column = next(column for column in history.columns if "日期" in str(column))
        nav_column = next(column for column in history.columns if "净值" in str(column))
        points = [
            (item[date_column].date(), float(item[nav_column]))
            for _, item in history.iterrows()
            if item[nav_column] is not None
        ]
        if not points:
            raise RuntimeError("公开数据源没有返回净值")
        return FundData(
            fund_code=fund_code,
            fund_name=fund_name,
            fund_type=infer_type(fund_name),
            share_class=infer_share_class(fund_name),
            source=self.name,
            nav_points=points,
        )


class ProviderChain:
    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self.demo = DemoProvider()

    @property
    def status(self) -> str:
        if self.mode == "demo":
            return "demo"
        try:
            import akshare  # noqa: F401

            return "akshare"
        except ImportError:
            return "demo_fallback"

    def load(self, fund_code: str) -> FundData:
        if self.mode == "demo":
            return self.demo.load(fund_code)
        try:
            return AkshareProvider().load(fund_code)
        except Exception:
            if self.mode == "akshare":
                raise
            return self.demo.load(fund_code)
