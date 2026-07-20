from __future__ import annotations

from fundlab.domain.enums import FundType


def classify_fund_name(name: str) -> FundType:
    """保守的名称分类器。

    名称只能作为缺少正式类型字段时的降级方案，所以无法判断时必须返回 UNKNOWN。
    """

    normalized = name.lower()
    if any(word in normalized for word in ("货币", "现金宝")):
        return FundType.MONEY
    if any(word in normalized for word in ("qdii", "纳斯达克", "标普", "海外")):
        return FundType.QDII
    if any(word in normalized for word in ("黄金", "商品")):
        return FundType.COMMODITY
    if "reits" in normalized or "reit" in normalized:
        return FundType.REIT
    if any(word in normalized for word in ("债券", "纯债", "短债", "中短债")):
        return FundType.BOND
    if any(word in normalized for word in ("指数", "etf", "联接")):
        return FundType.INDEX
    if any(word in normalized for word in ("混合", "股票", "成长", "价值", "精选")):
        return FundType.ACTIVE_EQUITY
    if "fof" in normalized:
        return FundType.FOF
    return FundType.UNKNOWN


def infer_share_class(name: str) -> str:
    for marker in ("A", "C", "E", "I"):
        if name.upper().endswith(marker) or name.endswith(f"（{marker}）"):
            return marker
    return "default"
