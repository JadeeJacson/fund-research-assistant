from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from fundlab.domain.enums import DataQuality
from fundlab.domain.models import FundProfile, NavRecord

from .classification import classify_fund_name, infer_share_class


class AKShareFundProvider:
    """AKShare 公募基金适配器。

    上游网页字段可能发生变化，因此所有列名处理都集中在本文件。页面和分析层不得
    直接调用 AKShare。接口失败时由 Service 回退到 SQLite 缓存。
    """

    name = "akshare"

    def __init__(self, ak_module: Any | None = None):
        if ak_module is None:
            try:
                import akshare as ak_module  # type: ignore[no-redef]
            except ImportError as exc:
                raise RuntimeError("尚未安装 AKShare，请先执行项目安装命令") from exc
        self.ak = ak_module

    def health_check(self) -> tuple[bool, str]:
        try:
            frame = self.ak.fund_open_fund_daily_em()
            return (not frame.empty, f"返回 {len(frame)} 条开放式基金记录")
        except Exception as exc:  # 上游异常类型不稳定，边界层统一转换
            return False, f"AKShare 不可用：{exc}"

    def get_fund_profile(self, fund_code: str) -> FundProfile:
        code = self._validate_code(fund_code)
        frame = self.ak.fund_open_fund_daily_em()
        if "基金代码" not in frame.columns:
            raise RuntimeError("AKShare 返回结果缺少“基金代码”字段")
        matches = frame[frame["基金代码"].astype(str).str.zfill(6) == code]
        if matches.empty:
            raise ValueError(f"未找到基金代码 {code}")
        row = matches.iloc[0]
        name = str(row.get("基金简称") or row.get("基金名称") or code)
        return FundProfile(
            fund_code=code,
            share_class=infer_share_class(name),
            fund_name=name,
            fund_type=classify_fund_name(name),
            source=self.name,
            fetched_at=datetime.now(UTC),
        )

    def get_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[NavRecord]:
        code = self._validate_code(fund_code)
        profile = self.get_fund_profile(code)
        frame = self.ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if frame.empty:
            raise ValueError(f"基金 {code} 没有可用净值数据")

        date_column = self._first_column(frame, ("净值日期", "日期", "x"))
        nav_column = self._first_column(frame, ("单位净值", "y"))
        dates = pd.to_datetime(frame[date_column], errors="coerce").dt.date
        navs = pd.to_numeric(frame[nav_column], errors="coerce")
        fetched_at = datetime.now(UTC)
        records: list[NavRecord] = []
        for nav_date, unit_nav in zip(dates, navs, strict=True):
            if pd.isna(nav_date) or pd.isna(unit_nav) or float(unit_nav) <= 0:
                continue
            if start_date and nav_date < start_date:
                continue
            if end_date and nav_date > end_date:
                continue
            records.append(
                NavRecord(
                    fund_id=profile.fund_id,
                    nav_date=nav_date,
                    unit_nav=float(unit_nav),
                    # 单位净值序列未必包含分红再投资。后续若取得复权序列，应写入 adjusted_nav。
                    source=self.name,
                    fetched_at=fetched_at,
                    quality_status=DataQuality.OK,
                )
            )
        records.sort(key=lambda item: item.nav_date)
        if not records:
            raise ValueError(f"基金 {code} 的净值在指定区间内为空")
        return records

    @staticmethod
    def _validate_code(fund_code: str) -> str:
        code = str(fund_code).strip()
        if not code.isdigit() or len(code) != 6:
            raise ValueError("基金代码必须是 6 位数字")
        return code

    @staticmethod
    def _first_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
        for column in candidates:
            if column in frame.columns:
                return column
        raise RuntimeError(f"AKShare 字段发生变化，未找到候选列：{candidates}")
