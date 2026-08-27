from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Protocol

import httpx


@dataclass(frozen=True, slots=True)
class FundPayload:
    code: str
    name: str
    share_class: str
    fund_type: str
    subtype: str
    peer_key: str
    default_bucket: str
    unit_nav: list[tuple[date, float]]
    cumulative_nav: list[tuple[date, float]]
    peer_percentile_history: list[tuple[date, float]] = field(default_factory=list)
    peer_percentile: float | None = None
    purchase_status: str = "unknown"
    redemption_status: str = "unknown"
    inception_date: date | None = None
    aum_yi: float | None = None
    expense_ratio: float | None = None
    manager: str = ""
    benchmark: str = ""
    tracked_index: str = ""
    currency: str = "CNY"
    valuation_lag_note: str = ""
    target_risk: str = ""
    product_status: str = "active"
    tracking_error: float | None = None
    return_method: str = "cumulative_nav"
    source_name: str = ""
    source_url: str = ""
    quality_status: str = "limited"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class AnnouncementPayload:
    title: str
    published_at: date
    source_url: str
    source_level: str
    event_type: str
    severity: str
    verified: bool
    content: str = ""


class MarketProvider(Protocol):
    name: str

    def load_fund(self, code: str) -> FundPayload: ...

    def load_announcements(self, code: str) -> list[AnnouncementPayload]: ...

    def list_peer_codes(self, current: FundPayload, limit: int = 50) -> list[str]: ...

    def resolve_fund_names(self, text: str, limit: int = 30) -> list[tuple[str, str, float]]: ...


def infer_share_class(name: str) -> str:
    match = re.search(r"(?:联接|混合|债券|指数|FOF|基金)?([A-EI])(?:类)?$", name.upper())
    return match.group(1) if match else ""


def _match_text(value: str) -> str:
    cleaned = value.upper()
    for token in ("人民币份额", "人民币", "基金", "发起式", "发起", "成份"):
        cleaned = cleaned.replace(token, "")
    return re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", cleaned)


def match_fund_catalog(
    text: str,
    catalog: list[tuple[str, str]],
    limit: int = 30,
) -> list[tuple[str, str, float]]:
    """Resolve OCR name lines conservatively; ambiguous matches remain unresolved."""
    ignored = {"全部持有", "收益明细", "交易记录", "持有收益排序", "名称金额", "日收益", "持有收益", "累计收益"}
    normalized_ignored = {_match_text(item) for item in ignored}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = [(code, name, _match_text(name)) for code, name in catalog if re.fullmatch(r"\d{6}", code)]
    resolved: dict[str, tuple[str, str, float]] = {}
    for line in lines:
        normalized_line = _match_text(line)
        if len(normalized_line) < 5 or normalized_line in normalized_ignored:
            continue
        scored: list[tuple[float, str, str]] = []
        for code, name, normalized_name in candidates:
            if len(normalized_name) < 5:
                continue
            exact = normalized_name in normalized_line or normalized_line in normalized_name
            same_manager = normalized_line[:4] == normalized_name[:4]
            if not exact and not same_manager:
                continue
            score = 1.0 if normalized_line == normalized_name else SequenceMatcher(None, normalized_line, normalized_name).ratio()
            if exact:
                score = max(score, min(len(normalized_line), len(normalized_name)) / max(len(normalized_line), len(normalized_name)))
            if score >= 0.68:
                scored.append((score, code, name))
        if not scored:
            continue
        scored.sort(reverse=True)
        best = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        if best[0] < 0.82 and best[0] - second_score < 0.025:
            continue
        previous = resolved.get(best[1])
        if previous is None or best[0] > previous[2]:
            resolved[best[1]] = (best[1], best[2], round(best[0], 4))
    return sorted(resolved.values(), key=lambda item: item[2], reverse=True)[:limit]


def infer_type(name: str) -> tuple[str, str]:
    upper = name.upper()
    if "REIT" in upper:
        return "reit", "public_reit"
    if "FOF" in upper or "养老" in name:
        return "fof", "fof"
    if "黄金" in name or "原油" in name or "商品" in name or "油气" in name:
        return "commodity", "gold" if "黄金" in name else "commodity"
    if "QDII" in upper or any(word in name for word in ("恒生", "纳斯达克", "标普", "中概", "海外", "全球")):
        return "qdii", "qdii_index" if "指数" in name or "ETF" in upper else "qdii_active"
    if "货币" in name:
        return "money", "money"
    if "同业存单" in name:
        return "deposit_index", "deposit_index"
    if "债" in name:
        if "短债" in name or "中短债" in name:
            return "bond", "short_bond"
        if "二级" in name or "可转债" in name:
            return "bond", "enhanced_bond"
        return "bond", "bond"
    if "ETF" in upper or "指数" in name or "联接" in name:
        return "index", "broad_index" if any(word in name for word in ("沪深300", "中证A500", "上证50", "红利", "宽基")) else "thematic_index"
    if "混合" in name:
        return "mixed", "mixed"
    if "股票" in name:
        return "active_equity", "active_equity"
    return "unknown", "unknown"


def default_bucket(fund_type: str, subtype: str, name: str) -> str:
    if fund_type in {"money", "deposit_index"} or subtype == "short_bond":
        return "defense"
    if subtype in {"broad_index", "bond", "enhanced_bond", "fof"} or any(word in name for word in ("红利", "低波", "稳健")):
        return "core"
    return "satellite"


def peer_key(fund_type: str, subtype: str, name: str) -> str:
    if fund_type == "index":
        for token in ("沪深300", "中证A500", "上证50", "创业板", "科创", "红利", "机器人", "芯片", "医药", "新能源"):
            if token in name:
                return f"index:{token}"
    if fund_type == "qdii":
        for token in ("恒生科技", "中概互联网", "纳斯达克", "标普500", "日经", "德国", "印度"):
            if token in name:
                return f"qdii:{token}"
    if fund_type == "commodity":
        return "commodity:gold" if "黄金" in name else "commodity:general"
    return f"{fund_type}:{subtype}"


def classify_event(title: str) -> tuple[str, str]:
    rules = (
        (("清算", "终止基金合同", "基金合同终止"), "liquidation", "critical"),
        (("合并",), "merger", "high"),
        (("暂停赎回", "暂停办理赎回"), "redemption_suspension", "critical"),
        (("基金经理变更", "基金经理离任", "解聘基金经理"), "manager_departure", "high"),
        (("指数编制方案", "指数规则", "编制规则"), "index_rule_change", "high"),
    )
    for words, event_type, severity in rules:
        if any(word in title for word in words):
            return event_type, severity
    return "other", "info"


def _to_date(value) -> date | None:
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


class AkshareProvider:
    name = "AKShare（聚合公开数据）"

    def __init__(self) -> None:
        self._catalog = None
        self._daily = None

    def _fund_catalog(self):
        if self._catalog is None:
            import akshare as ak

            self._catalog = ak.fund_name_em()
        return self._catalog

    def _daily_facts(self):
        if self._daily is None:
            import akshare as ak

            self._daily = ak.fund_open_fund_daily_em()
        return self._daily

    @staticmethod
    def _basic_facts(code: str) -> dict:
        import akshare as ak

        try:
            frame = ak.fund_individual_basic_info_xq(symbol=code, timeout=15)
            values = {str(row["item"]): row["value"] for _, row in frame.iterrows()}
            return {
                "inception_date": _to_date(values.get("成立时间")),
                "aum_yi": _to_float(values.get("最新规模")),
                "manager": "" if str(values.get("基金经理", "")) == "<NA>" else str(values.get("基金经理", "")),
                "benchmark": "" if str(values.get("业绩比较基准", "")) == "<NA>" else str(values.get("业绩比较基准", "")),
            }
        except Exception:
            return {"inception_date": None, "aum_yi": None, "manager": "", "benchmark": ""}

    def load_fund(self, code: str) -> FundPayload:
        import akshare as ak

        names = self._fund_catalog()
        row = names.loc[names["基金代码"].astype(str).str.zfill(6) == code]
        if row.empty:
            raise LookupError(f"未找到基金代码 {code}")
        name = str(row.iloc[0].get("基金简称") or row.iloc[0].get("基金名称") or f"基金 {code}")
        fund_type, subtype = infer_type(name)
        if fund_type == "money":
            return self._load_money_fund(code, name, fund_type, subtype)
        basic = self._basic_facts(code)
        unit = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        cumulative = ak.fund_open_fund_info_em(symbol=code, indicator="累计净值走势")
        unit_points = self._points(unit, "单位净值")
        cumulative_points = self._points(cumulative, "累计净值")
        if not unit_points:
            raise RuntimeError("公开数据源没有返回净值")

        rank_value = None
        rank_history: list[tuple[date, float]] = []
        try:
            ranks = ak.fund_open_fund_info_em(symbol=code, indicator="同类排名百分比")
            if not ranks.empty:
                date_col = next((column for column in ranks.columns if "日期" in str(column)), ranks.columns[0])
                value_col = ranks.columns[-1]
                for _, rank in ranks.iterrows():
                    rank_day, rank_value_item = _to_date(rank[date_col]), _to_float(rank[value_col])
                    if rank_day is not None and rank_value_item is not None:
                        rank_history.append((rank_day, rank_value_item))
                rank_history = sorted(set(rank_history))
                rank_value = rank_history[-1][1] if rank_history else None
        except Exception:
            pass

        purchase_status = redemption_status = "unknown"
        try:
            daily = self._daily_facts()
            daily_row = daily.loc[daily["基金代码"].astype(str).str.zfill(6) == code]
            if not daily_row.empty:
                current = daily_row.iloc[0]
                purchase_status = str(current.get("申购状态", "unknown"))
                redemption_status = str(current.get("赎回状态", "unknown"))
        except Exception:
            pass

        return FundPayload(
            code=code,
            name=name,
            share_class=infer_share_class(name),
            fund_type=fund_type,
            subtype=subtype,
            peer_key=peer_key(fund_type, subtype, name),
            default_bucket=default_bucket(fund_type, subtype, name),
            unit_nav=unit_points,
            cumulative_nav=cumulative_points,
            peer_percentile_history=rank_history,
            peer_percentile=rank_value,
            purchase_status=purchase_status,
            redemption_status=redemption_status,
            inception_date=basic["inception_date"],
            aum_yi=basic["aum_yi"],
            manager=basic["manager"],
            benchmark=basic["benchmark"],
            currency="MULTI" if fund_type == "qdii" else "CNY",
            valuation_lag_note="海外市场休市、汇率和估值时差可能导致净值日期滞后" if fund_type == "qdii" else "",
            source_name=self.name,
            source_url=f"https://fund.eastmoney.com/{code}.html",
            quality_status="ready" if len(cumulative_points) >= 60 else "limited",
        )

    def _load_money_fund(self, code: str, name: str, fund_type: str, subtype: str) -> FundPayload:
        basic = self._basic_facts(code)
        url = "https://api.fund.eastmoney.com/f10/lsjz"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html",
            "Host": "api.fund.eastmoney.com",
        }
        rows: list[dict] = []
        with httpx.Client(timeout=15) as client:
            for page in range(1, 6):
                response = client.get(
                    url,
                    headers=headers,
                    params={
                        "fundCode": code,
                        "pageIndex": str(page),
                        "pageSize": "20",
                        "startDate": "",
                        "endDate": "",
                        "_": round(time.time() * 1000),
                    },
                )
                response.raise_for_status()
                data = response.json().get("Data") or {}
                rows.extend(data.get("LSJZList") or [])
        income = sorted(
            (day, value)
            for row in rows
            if (day := _to_date(row.get("FSRQ"))) is not None
            and (value := _to_float(row.get("DWJZ"))) is not None
        )
        if len(income) < 60:
            raise RuntimeError("货币基金每万份收益历史不足 60 个观察值")
        growth = 1.0
        total_return_index: list[tuple[date, float]] = []
        for day, per_ten_thousand in income:
            growth *= 1 + per_ten_thousand / 10_000
            total_return_index.append((day, growth))
        latest = rows[0] if rows else {}
        return FundPayload(
            code=code,
            name=name,
            share_class=infer_share_class(name),
            fund_type=fund_type,
            subtype=subtype,
            peer_key=peer_key(fund_type, subtype, name),
            default_bucket=default_bucket(fund_type, subtype, name),
            unit_nav=[(day, 1.0) for day, _ in total_return_index],
            cumulative_nav=total_return_index,
            purchase_status=str(latest.get("SGZT") or "unknown"),
            redemption_status=str(latest.get("SHZT") or "unknown"),
            inception_date=basic["inception_date"],
            aum_yi=basic["aum_yi"],
            manager=basic["manager"],
            benchmark=basic["benchmark"],
            return_method="每万份收益按日复投构造的总回报指数",
            source_name=self.name,
            source_url=f"https://fundf10.eastmoney.com/jjjz_{code}.html",
            quality_status="ready",
        )

    def list_peer_codes(self, current: FundPayload, limit: int = 50) -> list[str]:
        names = self._fund_catalog()
        candidates: list[tuple[str, str]] = []
        for _, row in names.iterrows():
            code = str(row.get("基金代码", "")).zfill(6)
            name = str(row.get("基金简称") or row.get("基金名称") or "")
            if code == current.code or not re.fullmatch(r"\d{6}", code):
                continue
            fund_type, subtype = infer_type(name)
            if peer_key(fund_type, subtype, name) == current.peer_key:
                candidates.append((code, name))
        return [code for code, _ in sorted(candidates, key=lambda item: item[0])[:limit]]

    def resolve_fund_names(self, text: str, limit: int = 30) -> list[tuple[str, str, float]]:
        names = self._fund_catalog()
        catalog = [
            (str(row.get("基金代码", "")).zfill(6), str(row.get("基金简称") or row.get("基金名称") or ""))
            for _, row in names.iterrows()
        ]
        return match_fund_catalog(text, catalog, limit)

    @staticmethod
    def _points(frame, preferred: str) -> list[tuple[date, float]]:
        if frame is None or frame.empty:
            return []
        date_col = next((c for c in frame.columns if "日期" in str(c)), frame.columns[0])
        value_col = next((c for c in frame.columns if preferred in str(c)), frame.columns[1])
        points = []
        for _, item in frame.iterrows():
            day, value = _to_date(item[date_col]), _to_float(item[value_col])
            if day and value and value > 0:
                points.append((day, value))
        return sorted(set(points))

    def load_announcements(self, code: str) -> list[AnnouncementPayload]:
        import akshare as ak

        output: list[AnnouncementPayload] = []
        for loader in (ak.fund_announcement_report_em, ak.fund_announcement_dividend_em):
            try:
                frame = loader(symbol=code)
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            for _, row in frame.tail(30).iterrows():
                title = str(row.get("公告标题", ""))
                published = _to_date(row.get("公告日期"))
                report_id = str(row.get("报告ID", ""))
                if not title or not published:
                    continue
                event_type, severity = classify_event(title)
                output.append(AnnouncementPayload(
                    title=title,
                    published_at=published,
                    source_url=f"https://pdf.dfcfw.com/pdf/H2_{report_id}_1.pdf" if report_id else f"https://fundf10.eastmoney.com/jjgg_{code}.html",
                    source_level="A",
                    event_type=event_type,
                    severity=severity,
                    verified=False,
                ))
        unique = {(item.title, item.published_at): item for item in output}
        return sorted(unique.values(), key=lambda item: item.published_at, reverse=True)


class FixtureProvider:
    """仅供测试或显式演示；生产模式不会自动回退到这里。"""

    name = "固定测试数据"

    def load_fund(self, code: str) -> FundPayload:
        catalog = {
            "000001": "华夏成长混合A",
            "017470": "嘉实上证科创板芯片ETF联接C",
            "017471": "华夏中证芯片ETF联接A",
            "017472": "华安中证芯片ETF联接C",
            "019028": "广发添福30天持有期债券C",
            "013308": "易方达恒生科技ETF联接(QDII)A",
            "000009": "易方达天天理财货币A",
            "000216": "华安黄金易ETF联接A",
            "006289": "华夏养老2040三年持有混合FOF",
        }
        name = catalog.get(code, f"测试基金 {code}")
        fund_type, subtype = infer_type(name)
        end = date.today()
        seed = int(code[-3:]) or 7
        points = []
        day = end
        trading_days: list[date] = []
        while len(trading_days) < 380:
            if day.weekday() < 5:
                trading_days.append(day)
            day -= timedelta(days=1)
        for index, day in enumerate(reversed(trading_days)):
            value = 1 + index * ((seed % 7) + 1) / 100_000 + math.sin(index / 19) * 0.018
            points.append((day, round(value, 5)))
        percentile = float(20 + seed % 60)
        return FundPayload(
            code=code,
            name=name,
            share_class=infer_share_class(name),
            fund_type=fund_type,
            subtype=subtype,
            peer_key=peer_key(fund_type, subtype, name),
            default_bucket=default_bucket(fund_type, subtype, name),
            unit_nav=points,
            cumulative_nav=points,
            peer_percentile_history=[(day, percentile) for day, _ in points],
            peer_percentile=percentile,
            purchase_status="开放申购",
            redemption_status="开放赎回",
            inception_date=end - timedelta(days=1200),
            aum_yi=float(1 + seed % 8),
            expense_ratio=0.006,
            source_name=self.name,
            source_url="fixture://fund",
            quality_status="fixture",
        )

    def load_announcements(self, code: str) -> list[AnnouncementPayload]:
        return []

    def list_peer_codes(self, current: FundPayload, limit: int = 50) -> list[str]:
        codes = ["017470", "017471", "017472"] if current.peer_key == "index:芯片" else []
        return [code for code in codes if code != current.code][:limit]

    def resolve_fund_names(self, text: str, limit: int = 30) -> list[tuple[str, str, float]]:
        catalog = [
            ("000001", "华夏成长混合A"),
            ("017470", "嘉实上证科创板芯片ETF发起联接C"),
            ("019028", "广发添福30天持有期债券C"),
            ("013308", "易方达恒生科技ETF联接(QDII)A"),
            ("000009", "易方达天天理财货币A"),
            ("000216", "华安黄金易ETF联接A"),
            ("006289", "华夏养老2040三年持有混合FOF"),
        ]
        return match_fund_catalog(text, catalog, limit)


def build_provider(mode: str) -> MarketProvider:
    if mode in {"fixture", "demo"}:
        return FixtureProvider()
    if mode != "akshare":
        raise ValueError(f"不支持的市场 Provider: {mode}")
    return AkshareProvider()
