from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .analytics import Metrics


@dataclass(frozen=True, slots=True)
class Finding:
    reason_type: str
    proposed_action: str
    severity: str
    title: str
    detail: str
    metrics: dict[str, Any]
    evidence_ids: list[int]


def bucket_allocation(items: list[dict], rules: dict) -> dict[str, dict]:
    total = sum(float(item["amount"]) for item in items)
    result: dict[str, dict] = {}
    for key, config in rules["buckets"].items():
        amount = sum(float(item["amount"]) for item in items if item["bucket"] == key)
        weight = amount / total if total else 0.0
        result[key] = {
            "key": key,
            "label": config["label"],
            "amount": round(amount, 2),
            "weight": round(weight, 6),
            "low": config["low"],
            "mid": config["mid"],
            "high": config["high"],
            "drawdown_reference": config["drawdown_reference"],
            "in_band": config["low"] <= weight <= config["high"],
            "deviation_from_band": round(
                config["low"] - weight if weight < config["low"] else weight - config["high"] if weight > config["high"] else 0,
                6,
            ),
        }
    return result


def evaluate_fund(
    *,
    fund: dict,
    bucket: str,
    metrics: Metrics | None,
    evidences: list[dict],
    rules: dict,
    data_quality: str,
    data_quality_detail: str = "",
) -> list[Finding]:
    if data_quality == "blocked" or metrics is None:
        return [Finding(
            reason_type="data_quality",
            proposed_action="observe",
            severity="high",
            title=f"{fund['name']} 数据不足",
            detail=data_quality_detail or "缺少可核验总回报序列或最新数据，停止基金质量与替代结论。",
            metrics={
                "fund_code": fund["code"],
                "actual_observations": metrics.observations if metrics else 0,
                "required_observations": int(rules["quality"]["min_observations"]),
            },
            evidence_ids=[],
        )]

    hard_types = set(rules["hard_risk_event_types"])
    hard = [
        item
        for item in evidences
        if item.get("verified")
        and item.get("source_level") in {"S", "A"}
        and item.get("evidence_kind") != "news"
        and item.get("event_type") in hard_types
    ]
    if fund["fund_type"] == "index" or fund.get("subtype") == "qdii_index":
        hard = [item for item in hard if item["event_type"] != "manager_departure"]
    if fund["fund_type"] in {"reit", "unsupported"}:
        if hard:
            return [
                Finding(
                    reason_type="hard_risk",
                    proposed_action="observe",
                    severity="high",
                    title=f"{fund['name']} 存在需核对的产品事件",
                    detail=f"{hard[0]['title']}。该品类当前只展示事实，不输出强操作结论。",
                    metrics={"fund_code": fund["code"], "event_type": hard[0]["event_type"]},
                    evidence_ids=[item["id"] for item in hard[:3]],
                )
            ]
        return []
    if hard:
        return [Finding(
            reason_type="hard_risk",
            proposed_action="exit_review",
            severity="critical",
            title=f"{fund['name']} 命中硬风险",
            detail=hard[0]["title"],
            metrics={"fund_code": fund["code"], "event_type": hard[0]["event_type"]},
            evidence_ids=[item["id"] for item in hard[:3]],
        )]

    percentile = fund.get("peer_percentile")
    if percentile is None or percentile > rules["quality"]["peer_percentile_max"]:
        return []
    required_days = int(rules["buckets"][bucket]["laggard_persistence_days"])
    laggard_days = int(fund.get("laggard_trading_days") or 0)
    if laggard_days < required_days:
        return []
    # 仓位回撤参考线只用于聚合仓位，不能充当单基金止损线。单基金在这里
    # 只使用风险调整收益、申赎状态和已核验事件作为第二触发维度。
    risk_bad = metrics.sharpe is not None and metrics.sharpe < 0
    status_bad = "暂停" in str(fund.get("redemption_status", ""))
    event_bad = any(item.get("severity") in {"high", "critical"} for item in evidences)
    if not (risk_bad or status_bad or event_bad):
        return []
    evidence_ids = [item["id"] for item in evidences if item.get("severity") in {"high", "critical"}][:3]
    return [Finding(
        reason_type="quality_deterioration",
        proposed_action="reduce" if risk_bad or status_bad else "observe",
        severity="high",
        title=f"{fund['name']} 质量需要复核",
        detail=f"同类分位连续 {laggard_days} 个净值交易日处于后 1/3，且风险、申赎或事件维度至少一项恶化。",
        metrics={"fund_code": fund["code"], "peer_percentile": percentile, "laggard_trading_days": laggard_days, **metrics.as_dict()},
        evidence_ids=evidence_ids,
    )]


def select_headlines(findings: list[Finding], evidences: list[dict], limit: int = 3) -> list[dict]:
    priority = {"data_quality": 0, "hard_risk": 1, "quality_deterioration": 2, "alternative": 3}
    selected: list[dict] = []
    seen: set[str] = set()
    severity_order = {"critical": 0, "high": 1, "medium": 2, "info": 3}
    for finding in sorted(findings, key=lambda item: (priority.get(item.reason_type, 9), severity_order.get(item.severity, 9))):
        key = f"{finding.reason_type}:{finding.title}"
        if key in seen:
            continue
        selected.append({
            "kind": "finding",
            "reason_type": finding.reason_type,
            "title": finding.title,
            "detail": finding.detail,
            "severity": finding.severity,
        })
        seen.add(key)
        if len(selected) == limit:
            return selected
    source_priority = {"S": 4, "A": 3, "B": 2, "C": 1}
    for evidence in sorted(
        evidences,
        key=lambda item: (
            item.get("verified", False),
            source_priority.get(item.get("source_level", "C"), 0),
            item.get("published_at", date.min),
        ),
        reverse=True,
    ):
        key = f"evidence:{evidence['title']}"
        if key in seen or evidence.get("source_level") == "C":
            continue
        selected.append({"kind": "event", "title": evidence["title"], "detail": evidence.get("event_type", "other"), "severity": evidence.get("severity", "info")})
        seen.add(key)
        if len(selected) == limit:
            break
    return selected


def compare_alternative(current: dict, candidate: dict, current_metrics: Metrics, candidate_metrics: Metrics, bucket: str, rules: dict) -> tuple[list[str], list[str]]:
    config = rules["alternative"]
    improvements: list[str] = []
    counterpoints: list[str] = []
    current_pct, candidate_pct = current.get("peer_percentile"), candidate.get("peer_percentile")
    if current_pct is not None and candidate_pct is not None and candidate_pct - current_pct >= config["peer_percentile_improvement"]:
        improvements.append(f"同类分位提高 {candidate_pct - current_pct:.1f} 点")
    if current_metrics.calmar is not None and current_metrics.calmar > 0 and candidate_metrics.calmar is not None and candidate_metrics.calmar >= current_metrics.calmar * (1 + config["risk_adjusted_improvement"]):
        improvements.append("卡玛比率改善至少 15%")
    if current_metrics.sharpe is not None and current_metrics.sharpe > 0 and candidate_metrics.sharpe is not None and candidate_metrics.sharpe >= current_metrics.sharpe * (1 + config["risk_adjusted_improvement"]):
        improvements.append("夏普比率改善至少 15%")
    dd_gap = abs(current_metrics.max_drawdown or 0) - abs(candidate_metrics.max_drawdown or 0)
    if dd_gap >= config["drawdown_improvement"][bucket]:
        improvements.append(f"最大回撤改善 {dd_gap:.1%}")
    current_fee, candidate_fee = current.get("expense_ratio"), candidate.get("expense_ratio")
    if current_fee is not None and candidate_fee is not None:
        if current_fee - candidate_fee >= config["expense_improvement"]:
            improvements.append(f"费率降低 {(current_fee - candidate_fee):.2%}")
        elif candidate_fee - current_fee > config["expense_improvement"]:
            counterpoints.append("候选费率明显更高")
    if abs(candidate_metrics.max_drawdown or 0) - abs(current_metrics.max_drawdown or 0) > config["drawdown_improvement"][bucket]:
        counterpoints.append("候选最大回撤明显更差")
    if candidate.get("quality_status") not in {"ready", "fixture"}:
        counterpoints.append("候选数据质量较低")
    return improvements, counterpoints
