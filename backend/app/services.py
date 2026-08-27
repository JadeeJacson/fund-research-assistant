from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from .analytics import Metrics, calculate_window_metrics
from .decision import (
    Finding,
    bucket_allocation,
    compare_alternative,
    evaluate_fund,
    select_headlines,
)
from .models import (
    AlternativeComparison,
    BucketAssignment,
    CandidateUniverseSnapshot,
    DiscoveryRun,
    Evidence,
    Fund,
    HoldingItem,
    HoldingSnapshot,
    NavPoint,
    PeerMetricPoint,
    Portfolio,
    ProviderSnapshot,
    ReviewDecision,
    ReviewItem,
    ReviewRun,
)
from .providers import FundPayload, MarketProvider


def fund_dict(fund: Fund) -> dict:
    return {column.name: getattr(fund, column.name) for column in fund.__table__.columns}


def ensure_portfolio(session: Session, default_budget: float) -> Portfolio:
    portfolio = session.get(Portfolio, 1)
    if portfolio is None:
        portfolio = Portfolio(id=1, capital_budget=default_budget)
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
    return portfolio


def ensure_fund(session: Session, code: str, name: str = "", fund_type: str = "unknown") -> Fund:
    fund = session.scalar(select(Fund).where(Fund.code == code))
    if fund is None:
        from .providers import default_bucket, infer_type, peer_key

        inferred_type, subtype = infer_type(name) if name else (fund_type, fund_type)
        actual_type = fund_type if fund_type != "unknown" else inferred_type
        fund = Fund(
            code=code,
            name=name or f"待刷新基金 {code}",
            fund_type=actual_type,
            subtype=subtype,
            peer_key=peer_key(actual_type, subtype, name),
            default_bucket=default_bucket(actual_type, subtype, name),
            quality_status="limited",
        )
        session.add(fund)
        session.flush()
    return fund


def persist_payload(session: Session, payload: FundPayload) -> Fund:
    fund = ensure_fund(session, payload.code, payload.name, payload.fund_type)
    for field in (
        "name", "share_class", "fund_type", "subtype", "peer_key", "default_bucket",
        "benchmark", "tracked_index", "manager", "purchase_status", "redemption_status",
        "currency", "valuation_lag_note", "target_risk", "product_status", "tracking_error",
        "return_method",
        "inception_date", "aum_yi", "expense_ratio", "peer_percentile", "source_name",
        "source_url", "quality_status",
    ):
        setattr(fund, field, getattr(payload, field))
    values = payload.cumulative_nav or payload.unit_nav
    fund.value_date = values[-1][0] if values else None
    fund.fetched_at = payload.fetched_at
    unit = dict(payload.unit_nav)
    cumulative = dict(payload.cumulative_nav)
    session.execute(delete(NavPoint).where(NavPoint.fund_id == fund.id))
    session.add_all([
        NavPoint(
            fund_id=fund.id,
            nav_date=day,
            unit_nav=unit.get(day),
            cumulative_nav=cumulative.get(day),
            source_name=payload.source_name,
            quality_status="ready" if cumulative.get(day) is not None else "limited",
        )
        for day in sorted(set(unit) | set(cumulative))[-1800:]
    ])
    session.execute(delete(PeerMetricPoint).where(PeerMetricPoint.fund_id == fund.id))
    session.add_all([
        PeerMetricPoint(
            fund_id=fund.id,
            metric_date=day,
            percentile=value,
            source_name=payload.source_name,
        )
        for day, value in payload.peer_percentile_history[-1800:]
    ])
    snapshot_payload = json.dumps({
        "code": payload.code,
        "name": payload.name,
        "fund_type": payload.fund_type,
        "value_date": fund.value_date.isoformat() if fund.value_date else None,
        "unit_observations": len(payload.unit_nav),
        "cumulative_observations": len(payload.cumulative_nav),
    }, ensure_ascii=False, sort_keys=True)
    session.add(ProviderSnapshot(
        fund_id=fund.id,
        provider=payload.source_name,
        data_kind="fund_refresh",
        value_date=fund.value_date,
        quality_status=payload.quality_status,
        payload_json=snapshot_payload,
        payload_hash=hashlib.sha256(snapshot_payload.encode()).hexdigest(),
    ))
    session.commit()
    session.refresh(fund)
    return fund


def _bounded_provider_call(callable_, *, timeout_seconds: int = 15, retries: int = 1):
    last_error: Exception | None = None
    for _ in range(retries + 1):
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(callable_)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            last_error = TimeoutError(f"Provider 请求超过 {timeout_seconds} 秒")
        except Exception as exc:
            last_error = exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    raise last_error or RuntimeError("Provider 请求失败")


def refresh_fund(session: Session, provider: MarketProvider, code: str) -> Fund:
    payload = _bounded_provider_call(lambda: provider.load_fund(code))
    return persist_payload(session, payload)


def prepare_peer_universe(
    session: Session,
    provider: MarketProvider,
    current: Fund,
    *,
    max_refresh: int = 12,
) -> dict:
    month_key = date.today().strftime("%Y-%m")
    cached = session.scalar(
        select(CandidateUniverseSnapshot).where(
            CandidateUniverseSnapshot.month_key == month_key,
            CandidateUniverseSnapshot.peer_key == current.peer_key,
        )
    )
    if cached is None:
        current_payload = _bounded_provider_call(lambda: provider.load_fund(current.code))
        codes = provider.list_peer_codes(current_payload, limit=50)
        raw = json.dumps(codes, ensure_ascii=False)
        cached = CandidateUniverseSnapshot(
            month_key=month_key,
            peer_key=current.peer_key,
            codes_json=raw,
            source_name=provider.name,
            content_hash=hashlib.sha256(raw.encode()).hexdigest(),
        )
        session.add(cached)
        session.commit()
    else:
        codes = json.loads(cached.codes_json)
    codes = [code for code in codes if code != current.code][:max_refresh]
    loaded: list[FundPayload] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {
            pool.submit(_bounded_provider_call, lambda candidate=code: provider.load_fund(candidate)): code
            for code in codes
        }
        for future in as_completed(jobs):
            try:
                loaded.append(future.result(timeout=15))
            except Exception:
                failures.append(jobs[future])
    for payload in loaded:
        persist_payload(session, payload)
    return {"month": month_key, "candidate_count": len(codes), "refreshed": len(loaded), "failed": failures}


def persist_announcements(session: Session, provider: MarketProvider, fund: Fund) -> list[Evidence]:
    announcements = _bounded_provider_call(lambda: provider.load_announcements(fund.code))
    for item in announcements:
        fingerprint = hashlib.sha256(
            f"{fund.code}|{item.title}|{item.published_at}|{item.source_url}|{item.content}".encode()
        ).hexdigest()
        if session.scalar(select(Evidence).where(Evidence.content_hash == fingerprint)):
            continue
        session.add(Evidence(
            fund_id=fund.id,
            evidence_kind="announcement",
            title=item.title,
            source_url=item.source_url,
            source_level=item.source_level,
            published_at=item.published_at,
            available_from=item.published_at,
            content=item.content,
            content_hash=fingerprint,
            event_type=item.event_type,
            severity=item.severity,
            verified=item.verified,
        ))
    session.commit()
    return list(session.scalars(select(Evidence).where(Evidence.fund_id == fund.id).order_by(Evidence.published_at.desc())))


def create_snapshot(session: Session, payload, rules: dict) -> HoldingSnapshot:
    portfolio = ensure_portfolio(session, rules["portfolio"]["default_budget"])
    snapshot = HoldingSnapshot(
        portfolio_id=portfolio.id,
        as_of_date=payload.as_of_date,
        total_market_value=sum(item.amount for item in payload.items),
        completeness=payload.completeness,
        source=payload.source,
        note=payload.note,
    )
    session.add(snapshot)
    session.flush()
    for item in payload.items:
        fund = ensure_fund(session, item.fund_code, item.fund_name)
        assignment = session.scalar(select(BucketAssignment).where(BucketAssignment.fund_id == fund.id))
        bucket = item.bucket or (assignment.bucket if assignment else fund.default_bucket)
        if item.bucket and payload.completeness == "complete":
            if assignment is None:
                assignment = BucketAssignment(
                    fund_id=fund.id,
                    bucket=item.bucket,
                    source="user",
                    note="随完整持仓快照确认",
                )
                session.add(assignment)
            else:
                assignment.bucket = item.bucket
                assignment.source = "user"
                assignment.assigned_at = datetime.now(UTC)
        session.add(HoldingItem(
            snapshot_id=snapshot.id,
            fund_id=fund.id,
            amount=item.amount,
            displayed_profit=item.displayed_profit,
            bucket=bucket,
            assignment_source="user" if item.bucket else "rule",
        ))
    session.commit()
    return session.scalar(select(HoldingSnapshot).options(selectinload(HoldingSnapshot.items).selectinload(HoldingItem.fund)).where(HoldingSnapshot.id == snapshot.id))


def latest_snapshot(session: Session, *, complete_only: bool = False) -> HoldingSnapshot | None:
    query = select(HoldingSnapshot).options(selectinload(HoldingSnapshot.items).selectinload(HoldingItem.fund))
    if complete_only:
        query = query.where(HoldingSnapshot.completeness == "complete")
    return session.scalar(query.order_by(HoldingSnapshot.as_of_date.desc(), HoldingSnapshot.id.desc()))


def snapshot_json(snapshot: HoldingSnapshot | None) -> dict | None:
    if snapshot is None:
        return None
    return {
        "id": snapshot.id,
        "as_of_date": snapshot.as_of_date.isoformat(),
        "total_market_value": snapshot.total_market_value,
        "completeness": snapshot.completeness,
        "source": snapshot.source,
        "note": snapshot.note,
        "created_at": snapshot.created_at.isoformat(),
        "items": [{
            "id": item.id,
            "fund_code": item.fund.code,
            "fund_name": item.fund.name,
            "fund_type": item.fund.fund_type,
            "amount": item.amount,
            "weight": item.amount / snapshot.total_market_value if snapshot.total_market_value else 0,
            "displayed_profit": item.displayed_profit,
            "bucket": item.bucket,
            "assignment_source": item.assignment_source,
            "quality_status": item.fund.quality_status,
            "value_date": item.fund.value_date.isoformat() if item.fund.value_date else None,
        } for item in snapshot.items],
    }


def _metrics(session: Session, fund: Fund, horizon: int) -> Metrics | None:
    rows = list(session.execute(
        select(NavPoint.nav_date, NavPoint.cumulative_nav, NavPoint.unit_nav)
        .where(NavPoint.fund_id == fund.id).order_by(NavPoint.nav_date)
    ))
    cumulative = [(day, value) for day, value, _ in rows if value is not None]
    if len(cumulative) < 2:
        return None
    return calculate_window_metrics(cumulative, horizon)


def _quality(fund: Fund, metrics: Metrics | None, bucket: str, rules: dict) -> tuple[str, str]:
    required = int(rules["quality"]["min_observations"])
    if metrics is None:
        return "blocked", f"没有可核验的累计净值序列：实际 0 个观察值，至少需要 {required} 个。"
    if metrics.observations < required:
        return (
            "blocked",
            f"累计净值观察值不足：实际 {metrics.observations} 个，至少需要 {required} 个；"
            f"当前仓位窗口为 {rules['buckets'][bucket]['horizon_days']} 个交易日。",
        )
    if fund.quality_status == "fixture":
        return "limited", "当前为显式测试数据，只能给出有限结论。"
    if fund.value_date is None:
        return "blocked", "累计净值存在，但缺少可核验的数据截止日期。"
    stale_limit = rules["quality"]["stale_qdii_trading_days"] if fund.fund_type == "qdii" else rules["quality"]["stale_domestic_trading_days"]
    age = trading_days_between(fund.value_date, date.today())
    if age > 20:
        return "blocked", f"最新净值日期为 {fund.value_date.isoformat()}，已滞后 {age} 个交易日。"
    if age > stale_limit * 2:
        return "limited", f"最新净值已滞后 {age} 个交易日，本次降低结论强度。"
    if fund.quality_status == "ready":
        return "ready", ""
    return "limited", "上游数据状态有限，本次不输出高强度质量结论。"


def _laggard_streak(session: Session, fund: Fund, threshold: float) -> int:
    values = list(session.execute(
        select(PeerMetricPoint.metric_date, PeerMetricPoint.percentile)
        .where(PeerMetricPoint.fund_id == fund.id)
        .order_by(PeerMetricPoint.metric_date.desc())
        .limit(300)
    ))
    streak = 0
    for _, percentile in values:
        if percentile > threshold:
            break
        streak += 1
    return streak


def run_fingerprint(snapshot: HoldingSnapshot, rule_hash: str) -> str:
    raw = json.dumps({
        "snapshot": snapshot.id,
        "as_of": snapshot.as_of_date.isoformat(),
        "items": [(item.fund_id, item.amount, item.bucket) for item in snapshot.items],
        "rule": rule_hash,
        "run_date": date.today().isoformat(),
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def trading_days_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    current = start + timedelta(days=1)
    count = 0
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _finding_in_cooldown(
    session: Session,
    finding: Finding,
    fund_id: int | None,
    rules: dict,
    as_of_date: date,
) -> bool:
    if finding.reason_type == "hard_risk":
        return False
    query = (
        select(ReviewItem, ReviewDecision)
        .join(ReviewDecision, ReviewDecision.item_id == ReviewItem.id)
        .where(ReviewItem.reason_type == finding.reason_type)
        .order_by(ReviewDecision.decided_at.desc())
    )
    query = query.where(ReviewItem.fund_id == fund_id) if fund_id is not None else query.where(ReviewItem.fund_id.is_(None))
    previous = session.execute(query.limit(1)).first()
    if previous is None:
        return False
    old_item, decision = previous
    cooldown = {
        "reject": int(rules["portfolio"]["reject_cooldown_days"]),
        "defer": int(rules["portfolio"]["defer_cooldown_days"]),
    }.get(decision.user_choice)
    if cooldown is None or trading_days_between(decision.decided_at.date(), as_of_date) >= cooldown:
        return False
    severity = {"info": 0, "medium": 1, "high": 2, "critical": 3}
    if severity.get(finding.severity, 0) > severity.get(old_item.severity, 0):
        return False
    old_evidence = set(json.loads(old_item.evidence_ids_json or "[]"))
    return not set(finding.evidence_ids) - old_evidence


def process_review(session: Session, provider: MarketProvider, run: ReviewRun, rules: dict) -> None:
    run.status = "running"
    run.started_at = datetime.now(UTC)
    run.progress = 5
    session.commit()
    snapshot = session.scalar(select(HoldingSnapshot).options(selectinload(HoldingSnapshot.items).selectinload(HoldingItem.fund)).where(HoldingSnapshot.id == run.snapshot_id))
    if snapshot is None or snapshot.completeness != "complete":
        run.status, run.data_quality, run.verdict = "failed", "blocked", "review"
        run.error = "缺少已确认的完整持仓快照"
        run.completed_at = datetime.now(UTC)
        session.commit()
        return

    summary = bucket_allocation([{"amount": item.amount, "bucket": item.bucket} for item in snapshot.items], rules)
    # 三仓比例与区间仍写入 bucket_summary 供用户查看，但仓位偏离不属于
    # 基金研究评估，不生成 finding、headline 或 review item。
    findings: list[Finding] = []
    all_evidence: list[dict] = []
    qualities: list[str] = []
    deadline = time.monotonic() + 120

    for index, item in enumerate(snapshot.items, start=1):
        fund = item.fund
        if time.monotonic() >= deadline:
            fund.quality_status = "blocked"
            qualities.append("blocked")
            findings.append(
                Finding(
                    reason_type="data_quality",
                    proposed_action="observe",
                    severity="high",
                    title=f"{fund.name} 数据不足",
                    detail="本次评估已达到 120 秒上限，该基金可在稍后单独重试。",
                    metrics={"fund_code": fund.code},
                    evidence_ids=[],
                )
            )
            continue
        try:
            fund = refresh_fund(session, provider, fund.code)
            evidence_rows = persist_announcements(session, provider, fund)
        except Exception as exc:
            evidence_rows = list(session.scalars(select(Evidence).where(Evidence.fund_id == fund.id)))
            fund.quality_status = "blocked" if fund.value_date is None else "limited"
            session.add(ProviderSnapshot(
                fund_id=fund.id, provider=getattr(provider, "name", "unknown"), data_kind="refresh_error",
                value_date=fund.value_date, quality_status="blocked", payload_json="{}",
                payload_hash=hashlib.sha256(f"{fund.code}|{date.today()}|{type(exc).__name__}".encode()).hexdigest(),
                error=f"{type(exc).__name__}: 公开数据刷新失败",
            ))
            session.commit()
        horizon = int(rules["buckets"][item.bucket]["horizon_days"])
        metrics = _metrics(session, fund, horizon)
        quality, quality_detail = _quality(fund, metrics, item.bucket, rules)
        qualities.append(quality)
        evidence_dicts = [{
            "id": evidence.id, "title": evidence.title, "published_at": evidence.published_at,
            "source_level": evidence.source_level, "event_type": evidence.event_type,
            "severity": evidence.severity, "verified": evidence.verified,
            "evidence_kind": evidence.evidence_kind,
        } for evidence in evidence_rows if evidence.available_from <= run.as_of_date]
        all_evidence.extend(evidence_dicts)
        evaluation_fund = fund_dict(fund)
        evaluation_fund["laggard_trading_days"] = _laggard_streak(
            session, fund, rules["quality"]["peer_percentile_max"]
        )
        findings.extend(evaluate_fund(
            fund=evaluation_fund, bucket=item.bucket, metrics=metrics, evidences=evidence_dicts,
            rules=rules, data_quality=quality, data_quality_detail=quality_detail,
        ))
        if quality != "blocked":
            with suppress(Exception):
                prepare_peer_universe(session, provider, fund, max_refresh=4)
            alternatives = alternatives_for(session, fund, item.bucket, rules, run.id)
            ready_alternatives = [candidate for candidate in alternatives if candidate["review_ready"]]
            if ready_alternatives:
                candidate = ready_alternatives[0]
                findings.append(
                    Finding(
                        reason_type="alternative",
                        proposed_action="compare",
                        severity="medium",
                        title=f"{fund.name} 出现可复核替代项",
                        detail=f"{candidate['fund']['name']} 已连续满足至少两项显著改善；请查看多维对照和反方证据。",
                        metrics={"fund_code": fund.code, "candidate_code": candidate["fund"]["code"]},
                        evidence_ids=[],
                    )
                )
        run.progress = min(80, 10 + int(index / max(len(snapshot.items), 1) * 70))
        session.commit()

    active_findings: list[Finding] = []
    for finding in findings:
        fund_id = None
        finding_code = finding.metrics.get("fund_code")
        for item in snapshot.items:
            if finding_code and item.fund.code == finding_code:
                fund_id = item.fund_id
                break
        if _finding_in_cooldown(session, finding, fund_id, rules, run.as_of_date):
            continue
        active_findings.append(finding)
        session.add(ReviewItem(
            run_id=run.id, fund_id=fund_id, reason_type=finding.reason_type,
            proposed_action=finding.proposed_action, severity=finding.severity,
            title=finding.title, detail=finding.detail,
            metric_json=json.dumps(finding.metrics, ensure_ascii=False, default=str),
            evidence_ids_json=json.dumps(finding.evidence_ids),
        ))
    run.bucket_summary_json = json.dumps(summary, ensure_ascii=False)
    run.headline_json = json.dumps(select_headlines(active_findings, all_evidence, rules["evidence"]["max_headline_items"]), ensure_ascii=False, default=str)
    run.verdict = "review" if active_findings else "hold"
    run.data_quality = "blocked" if "blocked" in qualities else "limited" if "limited" in qualities else "ready"
    run.status = "partial" if "blocked" in qualities else "completed"
    run.progress = 100
    run.completed_at = datetime.now(UTC)
    session.commit()


def review_json(run: ReviewRun) -> dict:
    # v2.1.2 起仓位偏离只作比例展示。数据库中的旧记录继续保留用于审计，
    # 但不会再占据当前或历史复核队列，也不会维持“需要复核”总判断。
    visible_items = [item for item in run.items if item.reason_type != "band_breach"]
    hidden_titles = {item.title for item in run.items if item.reason_type == "band_breach"}
    headlines = [
        item
        for item in json.loads(run.headline_json or "[]")
        if item.get("reason_type") != "band_breach" and item.get("title") not in hidden_titles
    ]
    verdict = run.verdict
    if verdict == "review" and not visible_items and hidden_titles and run.status != "failed" and run.data_quality != "blocked":
        verdict = "hold"
    return {
        "id": run.id,
        "snapshot_id": run.snapshot_id,
        "status": run.status,
        "progress": run.progress,
        "verdict": verdict,
        "verdict_label": "无需调整信号" if verdict == "hold" else "需要复核",
        "data_quality": run.data_quality,
        "as_of_date": run.as_of_date.isoformat(),
        "rule_version": run.rule_version,
        "bucket_summary": json.loads(run.bucket_summary_json or "{}"),
        "headlines": headlines,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "items": [{
            "id": item.id,
            "fund_code": item.fund.code if item.fund else None,
            "fund_name": item.fund.name if item.fund else None,
            "reason_type": item.reason_type,
            "proposed_action": item.proposed_action,
            "severity": item.severity,
            "title": item.title,
            "detail": item.detail,
            "metrics": json.loads(item.metric_json or "{}"),
            "evidence_ids": json.loads(item.evidence_ids_json or "[]"),
            "status": item.status,
            "decision": ({"choice": item.decision.user_choice, "note": item.decision.note, "decided_at": item.decision.decided_at.isoformat()} if item.decision else None),
        } for item in visible_items],
    }


def alternatives_for(session: Session, current: Fund, bucket: str, rules: dict, run_id: int | None = None) -> list[dict]:
    current_metrics = _metrics(session, current, int(rules["buckets"][bucket]["horizon_days"]))
    if current_metrics is None:
        return []
    peers = list(
        session.scalars(
            select(Fund)
            .where(Fund.id != current.id, Fund.peer_key == current.peer_key)
            .order_by(Fund.aum_yi.desc().nullslast(), Fund.expense_ratio.asc().nullslast(), Fund.code)
            .limit(50)
        )
    )
    results = []
    today = date.today()
    hard_risk = session.scalar(
        select(Evidence.id).where(
            Evidence.fund_id == current.id,
            Evidence.verified.is_(True),
            Evidence.event_type.in_(rules["hard_risk_event_types"]),
        )
    ) is not None
    for candidate in peers:
        age_years = (today - candidate.inception_date).days / 365.25 if candidate.inception_date else None
        if candidate.aum_yi is not None and candidate.aum_yi < rules["alternative"]["watch_min_aum_yi"]:
            continue
        if age_years is not None and age_years < rules["alternative"]["watch_min_age_years"]:
            continue
        candidate_metrics = _metrics(session, candidate, int(rules["buckets"][bucket]["horizon_days"]))
        if candidate_metrics is None:
            continue
        improvements, counterpoints = compare_alternative(fund_dict(current), fund_dict(candidate), current_metrics, candidate_metrics, bucket, rules)
        candidate_hard_risk = session.scalar(
            select(Evidence.id).where(
                Evidence.fund_id == candidate.id,
                Evidence.verified.is_(True),
                Evidence.event_type.in_(rules["hard_risk_event_types"]),
            )
        ) is not None
        if candidate_hard_risk:
            counterpoints.append("候选存在已核验硬风险")
        if candidate.product_status != "active":
            counterpoints.append(f"候选产品状态为 {candidate.product_status}")
        if any(token in candidate.redemption_status for token in ("暂停", "封闭", "不可赎回")):
            counterpoints.append(f"候选赎回状态为 {candidate.redemption_status}")
        if candidate.aum_yi is None or age_years is None:
            tier = "unknown"
            counterpoints.append("规模或成立年限缺失，只能作为风险标签展示")
        elif candidate.aum_yi >= rules["alternative"]["strong_min_aum_yi"] and age_years >= rules["alternative"]["strong_min_age_years"]:
            tier = "strong"
        else:
            tier = "watch"
            counterpoints.append("处于观察候选层，不能升级为替换复核")
        eligible = (
            tier == "strong"
            and len(improvements) >= rules["alternative"]["min_improvements"]
            and not counterpoints
        )
        previous = None
        if run_id is not None:
            previous = session.scalar(
                select(AlternativeComparison)
                .where(
                    AlternativeComparison.current_fund_id == current.id,
                    AlternativeComparison.candidate_fund_id == candidate.id,
                    AlternativeComparison.eligible.is_(True),
                    AlternativeComparison.run_id.is_not(None),
                )
                .order_by(AlternativeComparison.compared_at.desc())
            )
        persistence = 1 if eligible else 0
        if eligible and previous is not None:
            persistence = previous.persistence_count
            if trading_days_between(previous.compared_at.date(), today) >= 5:
                persistence += 1
        review_ready = run_id is not None and eligible and (hard_risk or persistence >= 2)
        if run_id is not None:
            session.add(AlternativeComparison(
                run_id=run_id, current_fund_id=current.id, candidate_fund_id=candidate.id,
                tier=tier, improvements_json=json.dumps(improvements, ensure_ascii=False),
                counterpoints_json=json.dumps(counterpoints, ensure_ascii=False), eligible=eligible,
                persistence_count=persistence,
            ))
        results.append({
            "fund": fund_dict(candidate), "tier": tier, "eligible": eligible,
            "review_ready": review_ready, "persistence_count": persistence,
            "improvements": improvements, "counterpoints": counterpoints,
            "metrics": candidate_metrics.as_dict(),
        })
    session.commit()
    results.sort(key=lambda item: (not item["eligible"], -len(item["improvements"]), item["fund"]["code"]))
    return results[: rules["alternative"]["max_results"]]


def process_discovery(
    session: Session,
    provider: MarketProvider,
    run: DiscoveryRun,
    rules: dict,
) -> None:
    """Explore auditable peers around the current portfolio without selecting a champion."""
    run.status = "running"
    run.started_at = datetime.now(UTC)
    run.progress = 5
    session.commit()
    snapshot = session.scalar(
        select(HoldingSnapshot)
        .options(selectinload(HoldingSnapshot.items).selectinload(HoldingItem.fund))
        .where(HoldingSnapshot.id == run.snapshot_id)
    )
    if snapshot is None or snapshot.completeness != "complete":
        run.status = "failed"
        run.error = "缺少已确认的完整持仓快照"
        run.completed_at = datetime.now(UTC)
        session.commit()
        return

    held_codes = {item.fund.code for item in snapshot.items}
    candidates: dict[str, dict] = {}
    failures: list[str] = []
    deadline = time.monotonic() + 180
    for index, holding in enumerate(snapshot.items, start=1):
        if time.monotonic() >= deadline:
            failures.append("本次探索达到 180 秒上限，其余持仓可下次继续探索")
            break
        try:
            current = refresh_fund(session, provider, holding.fund.code)
            prepare_peer_universe(session, provider, current, max_refresh=8)
            comparisons = alternatives_for(session, current, holding.bucket, rules)
        except Exception:
            failures.append(f"{holding.fund.code} 同类数据刷新失败")
            comparisons = []
        for comparison in comparisons:
            candidate = comparison["fund"]
            code = candidate["code"]
            if code in held_codes or len(comparison["improvements"]) < rules["alternative"]["min_improvements"]:
                continue
            item = {
                **comparison,
                "bucket": holding.bucket,
                "compared_to": {
                    "code": holding.fund.code,
                    "name": holding.fund.name,
                },
                "suggestion": "值得进一步对照" if comparison["eligible"] else "观察候选",
                "review_ready": False,
            }
            previous = candidates.get(code)
            if previous is None or (
                comparison["eligible"],
                len(comparison["improvements"]),
                -len(comparison["counterpoints"]),
            ) > (
                previous["eligible"],
                len(previous["improvements"]),
                -len(previous["counterpoints"]),
            ):
                candidates[code] = item
        run.progress = min(90, 10 + int(index / max(len(snapshot.items), 1) * 80))
        session.commit()

    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            not item["eligible"],
            -len(item["improvements"]),
            len(item["counterpoints"]),
            item["fund"]["code"],
        ),
    )
    selected: list[dict] = []
    per_bucket: dict[str, int] = {"defense": 0, "core": 0, "satellite": 0}
    for item in ordered:
        if per_bucket[item["bucket"]] >= 2 or len(selected) >= 6:
            continue
        selected.append(item)
        per_bucket[item["bucket"]] += 1
    run.result_json = json.dumps(selected, ensure_ascii=False, default=str)
    run.error = "；".join(failures)
    run.status = "partial" if failures else "completed"
    run.progress = 100
    run.completed_at = datetime.now(UTC)
    session.commit()


def discovery_json(run: DiscoveryRun) -> dict:
    return {
        "id": run.id,
        "snapshot_id": run.snapshot_id,
        "status": run.status,
        "progress": run.progress,
        "rule_version": run.rule_version,
        "results": json.loads(run.result_json or "[]"),
        "error": run.error,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
