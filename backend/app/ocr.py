from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


@dataclass(slots=True)
class DraftItem:
    kind: str
    fund_code: str = ""
    fund_name: str = ""
    amount: float | None = None
    displayed_profit: float | None = None
    confidence: float = 0.0
    issues: str = ""


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("基金|", "").replace("基金｜", "")


def classify_page(text: str) -> str:
    compact = _normalize_name(text)
    if "基金自选" in compact:
        return "candidates"
    if "全部持有" in compact or "资产构成" in compact or "持有收益" in compact:
        return "holdings"
    if re.search(r"\b\d{6}\b", text):
        return "candidates"
    return "unknown"


def _match_known_funds(
    text: str,
    resolved_funds: list[tuple[str, str, float]] | None = None,
) -> list[tuple[str, str, float]]:
    matches: list[tuple[str, str, float]] = []
    for code in re.findall(r"(?<!\d)(\d{6})(?!\d)", text):
        if code not in {item[0] for item in matches}:
            matches.append((code, f"待刷新基金 {code}", 0.86))
    for code, name, confidence in resolved_funds or []:
        existing = next((index for index, item in enumerate(matches) if item[0] == code), None)
        if existing is None:
            matches.append((code, name, confidence))
        else:
            matches[existing] = (code, name, confidence)
    return matches


def _number_after_label(text: str, labels: tuple[str, ...]) -> float | None:
    normalized = text.replace("−", "-").replace("－", "-").replace("＋", "+")
    number = r"([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)"
    for label in labels:
        # A column heading elsewhere on the screenshot must not consume a value
        # from a later product row. Only accept a labelled value on the same OCR line.
        pattern = re.compile(rf"{re.escape(label)}[^\d+\-\r\n]{{0,18}}{number}")
        for match in pattern.finditer(normalized):
            tail = normalized[match.end() : match.end() + 2]
            if "%" in tail or "％" in tail:
                continue
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _fund_text_windows(text: str, matches: list[tuple[str, str, float]]) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    anchors: list[tuple[int, str]] = []
    for code, name, _ in matches:
        code_line = next(
            (index for index, line in enumerate(lines) if re.search(rf"(?<!\d){code}(?!\d)", line)),
            None,
        )
        if code_line is not None:
            anchors.append((code_line, code))
            continue
        normalized_name = _normalize_name(name).upper()
        scored = [
            (SequenceMatcher(None, _normalize_name(line).upper(), normalized_name).ratio(), index)
            for index, line in enumerate(lines)
            if len(_normalize_name(line)) >= 5
        ]
        if scored:
            score, line_index = max(scored)
            if score >= 0.65:
                anchors.append((line_index, code))
    anchors.sort()
    windows: dict[str, str] = {}
    for position, (line_index, code) in enumerate(anchors):
        next_index = anchors[position + 1][0] if position + 1 < len(anchors) else len(lines)
        windows[code] = "\n".join(lines[line_index:next_index])
    return windows


def _positional_currency_values(text: str) -> list[float]:
    values: list[float] = []
    pattern = re.compile(r"^[+\-−－＋]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?:元)?$")
    for raw_line in text.splitlines():
        line = raw_line.strip().replace("−", "-").replace("－", "-").replace("＋", "+")
        if not pattern.fullmatch(line) or "%" in line or "％" in line:
            continue
        try:
            values.append(float(line.removesuffix("元").replace(",", "")))
        except ValueError:
            continue
    return values


def parse_ocr_text(
    text: str,
    resolved_funds: list[tuple[str, str, float]] | None = None,
) -> tuple[str, list[DraftItem]]:
    page_type = classify_page(text)
    matches = _match_known_funds(text, resolved_funds)
    items: list[DraftItem] = []
    if page_type == "candidates":
        for code, name, confidence in matches:
            items.append(
                DraftItem(
                    kind="candidate",
                    fund_code=code,
                    fund_name=name,
                    confidence=confidence,
                    issues="请核对份额类别与完整名称",
                )
            )
    elif page_type == "holdings":
        windows = _fund_text_windows(text, matches)
        for code, name, confidence in matches:
            window = windows.get(code, text)
            amount = _number_after_label(window, ("持有金额", "持有资产", "资产金额", "当前市值", "市值"))
            displayed_profit = _number_after_label(window, ("持有收益", "累计收益", "收益金额"))
            positional = _positional_currency_values(window)
            if amount is None and positional:
                amount = positional[0]
            if displayed_profit is None and len(positional) >= 3:
                displayed_profit = positional[2]
            detected = []
            if amount is not None:
                detected.append("持仓金额")
            if displayed_profit is not None:
                detected.append("持有收益")
            items.append(
                DraftItem(
                    kind="holding",
                    fund_code=code,
                    fund_name=name,
                    amount=amount,
                    displayed_profit=displayed_profit,
                    confidence=min(confidence, 0.72 if amount is not None else 0.45),
                    issues=(
                        f"已按标签提取{'和'.join(detected)}，必须人工核对；个人收益只展示，不参与基金质量判断"
                        if detected
                        else "未可靠识别金额或收益，请人工填写；截图是快照，不等于交易成本"
                    ),
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

    def extract(self, path: Path) -> tuple[str, list[float], list[list]]:
        if self.engine is None:
            return "", [], []
        result = self.engine(str(path))
        raw_txts = getattr(result, "txts", None)
        raw_scores = getattr(result, "scores", None)
        raw_boxes = getattr(result, "boxes", None)
        txts = list(raw_txts) if raw_txts is not None else []
        scores = [float(value) for value in raw_scores] if raw_scores is not None else []
        boxes = [
            [[float(coordinate) for coordinate in point] for point in box]
            for box in (raw_boxes if raw_boxes is not None else [])
        ]
        if not txts and isinstance(result, tuple) and result:
            rows = result[0] or []
            txts = [str(row[1]) for row in rows]
            scores = [float(row[2]) for row in rows]
            boxes = [
                [[float(coordinate) for coordinate in point] for point in row[0]]
                for row in rows
            ]
        return "\n".join(txts), scores, boxes
