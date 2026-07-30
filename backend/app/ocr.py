from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from .providers import KNOWN_FUNDS


@dataclass(slots=True)
class DraftItem:
    kind: str
    fund_code: str = ""
    fund_name: str = ""
    action: str = ""
    amount: float | None = None
    shares: float | None = None
    event_time: datetime | None = None
    confidence: float = 0.0
    issues: str = ""


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("基金|", "").replace("基金｜", "")


def classify_page(text: str) -> str:
    compact = _normalize_name(text)
    if "基金自选" in compact:
        return "candidates"
    action_count = sum(compact.count(word) for word in ("买入", "卖出", "转换"))
    if action_count >= 2:
        return "transactions"
    if "全部持有" in compact or "资产构成" in compact or "持有收益" in compact:
        return "holdings"
    if "交易记录" in compact and action_count >= 1:
        return "transactions"
    if re.search(r"\b\d{6}\b", text):
        return "candidates"
    return "unknown"


def _match_known_funds(text: str) -> list[tuple[str, str]]:
    compact = _normalize_name(text)
    matches: list[tuple[str, str]] = []
    for code, (name, _, _) in KNOWN_FUNDS.items():
        stem = _normalize_name(name).replace("(QDII)", "")
        prefix = stem[: min(10, len(stem))]
        if code in text or prefix in compact:
            matches.append((code, name))
    for code in re.findall(r"(?<!\d)(\d{6})(?!\d)", text):
        if code not in {item[0] for item in matches}:
            name = KNOWN_FUNDS.get(code, (f"待核验基金 {code}", "", ""))[0]
            matches.append((code, name))
    return matches


def parse_ocr_text(text: str) -> tuple[str, list[DraftItem]]:
    page_type = classify_page(text)
    matches = _match_known_funds(text)
    items: list[DraftItem] = []
    if page_type == "candidates":
        for code, name in matches:
            items.append(
                DraftItem(
                    kind="candidate",
                    fund_code=code,
                    fund_name=name,
                    confidence=0.86 if code in text else 0.68,
                    issues="请核对份额类别与完整名称",
                )
            )
    elif page_type == "holdings":
        compact = _normalize_name(text)
        for code, name in matches:
            stem = _normalize_name(name).replace("(QDII)", "")[:12]
            position = compact.find(stem)
            window = compact[position : position + 90] if position >= 0 else compact
            numbers = re.findall(r"(?<![\d.-])(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)(?![%\d])", window)
            amount = float(numbers[0].replace(",", "")) if numbers else None
            items.append(
                DraftItem(
                    kind="holding",
                    fund_code=code,
                    fund_name=name,
                    amount=amount,
                    event_time=datetime.now(UTC),
                    confidence=0.62 if amount is not None else 0.45,
                    issues="金额来自版面邻近匹配，必须人工核对；截图是快照，不等于交易成本",
                )
            )
    elif page_type == "transactions":
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if re.match(r"^(买入|卖出|转换)(?:\s|$)", line):
                if current:
                    blocks.append(current)
                current = [line]
            elif current:
                current.append(line)
                if re.search(r"20\d{2}-\d{2}-\d{2}", line):
                    blocks.append(current)
                    current = []
        if current:
            blocks.append(current)
        for block in blocks:
            block_text = "\n".join(block)
            compact = _normalize_name(block_text)
            action_cn = next((word for word in ("转换", "卖出", "买入") if word in block[0]), "买入")
            amount_match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)(元|份)", compact)
            value = float(amount_match.group(1).replace(",", "")) if amount_match else None
            date_match = re.search(
                r"(20\d{2}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})",
                block_text,
            )
            event_time = None
            if date_match:
                event_time = datetime.fromisoformat(
                    f"{date_match.group(1)}T{date_match.group(2)}"
                ).replace(tzinfo=timezone(timedelta(hours=8)))
            block_matches = _match_known_funds(block_text)
            if not block_matches:
                name_match = re.search(r"[|｜](.+?)(?:\d+(?:,\d{3})*(?:\.\d+)?(?:元|份)|20\d{2}-)", compact)
                extracted = (name_match.group(1) if name_match else compact)[:80]
                block_matches = [("", extracted.replace("->", " → "))]
            for code, name in block_matches:
                action = {
                    "买入": "buy",
                    "卖出": "sell",
                    "转换": "convert_in" if code else "convert_out",
                }[action_cn]
                items.append(
                    DraftItem(
                        kind="transaction",
                        fund_code=code,
                        fund_name=name,
                        action=action,
                        amount=value if not amount_match or amount_match.group(2) == "元" else None,
                        shares=value if amount_match and amount_match.group(2) == "份" else None,
                        event_time=event_time,
                        confidence=0.68 if code and event_time and value is not None else 0.38,
                        issues="列表页通常缺少确认净值、份额或费用；无代码或转换记录必须人工补全",
                    )
                )
    if not items:
        items.append(
            DraftItem(
                kind="candidate",
                confidence=0.0,
                issues="未自动识别出完整记录，请人工填写后再确认",
            )
        )
    return page_type, items


class OCRService:
    def __init__(self):
        try:
            from rapidocr import RapidOCR

            self.engine = RapidOCR()
            self.available = True
        except ImportError:
            self.engine = None
            self.available = False

    def extract(self, path: Path) -> tuple[str, list[float]]:
        if self.engine is None:
            return "", []
        result = self.engine(str(path))
        txts = list(getattr(result, "txts", []) or [])
        scores = [float(value) for value in (getattr(result, "scores", []) or [])]
        if not txts and isinstance(result, tuple) and result:
            rows = result[0] or []
            txts = [str(row[1]) for row in rows]
            scores = [float(row[2]) for row in rows]
        return "\n".join(txts), scores
