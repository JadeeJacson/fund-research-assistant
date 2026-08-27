import hashlib
import json
import os
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from .ai import (
    AI_PROMPT_VERSION,
    AI_SCHEMA_VERSION,
    ai_configuration_status,
    explain_review,
    test_deepseek,
)
from .analytics import calculate_performance_chart, calculate_window_metrics
from .config import Settings, update_local_env
from .database import Database
from .decision import bucket_allocation
from .models import (
    AiRun,
    BucketAssignment,
    DiscoveryRun,
    Evidence,
    Fund,
    HoldingItem,
    HoldingSnapshot,
    IdempotencyRecord,
    ImportBatch,
    ImportItem,
    NavPoint,
    Portfolio,
    ProviderSnapshot,
    ReviewDecision,
    ReviewItem,
    ReviewRun,
)
from .ocr import OCRService, classify_page, parse_ocr_text
from .providers import MarketProvider, build_provider, classify_event, match_fund_catalog
from .schemas import (
    AiSettingsUpdate,
    BucketAssignmentUpdate,
    EvidenceCreate,
    FundEnsure,
    FundRead,
    ImportConfirm,
    PortfolioUpdate,
    ReviewDecisionCreate,
    SnapshotCreate,
)
from .services import (
    alternatives_for,
    create_snapshot,
    discovery_json,
    ensure_fund,
    ensure_portfolio,
    fund_dict,
    latest_snapshot,
    prepare_peer_universe,
    process_discovery,
    process_review,
    refresh_fund,
    review_json,
    run_fingerprint,
    snapshot_json,
)

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def create_app(*, database_url: str | None = None, project_root: Path | None = None, provider: MarketProvider | None = None) -> FastAPI:
    settings = Settings.from_env(project_root)
    if database_url is not None:
        settings = replace(settings, database_url=database_url)
    database = Database(settings.database_url)
    database.create_all()
    market_provider = provider or build_provider(settings.market_provider)
    ocr = OCRService()

    app = FastAPI(title="基金仓位决策台 API", version="2.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.database = database
    app.state.provider = market_provider
    app.state.ocr = ocr
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = exc.errors()
        if request.url.path == "/api/v2/settings/ai":
            details = [
                {key: value for key, value in error.items() if key in {"loc", "msg", "type"}}
                for error in details
            ]
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "输入内容未通过校验",
                        "details": details,
                    }
                }
            ),
        )

    def session_dependency():
        yield from database.session()

    DBSession = Annotated[Session, Depends(session_dependency)]

    with database.session_factory() as session:
        ensure_portfolio(session, settings.rule_config.values["portfolio"]["default_budget"])
        for run in session.scalars(select(ReviewRun).where(ReviewRun.status.in_(["queued", "running"]))):
            run.status = "failed"
            run.error = "应用重启中断，可重新运行评估"
            run.completed_at = datetime.now(UTC)
        for run in session.scalars(select(DiscoveryRun).where(DiscoveryRun.status.in_(["queued", "running"]))):
            run.status = "failed"
            run.error = "应用重启中断，可重新运行探索"
            run.completed_at = datetime.now(UTC)
        session.commit()

    def idempotency_lookup(
        session: Session,
        request: Request,
        operation: str,
        payload: object,
    ) -> tuple[dict | None, str, str]:
        key = request.headers.get("Idempotency-Key", "").strip()
        request_json = json.dumps(jsonable_encoder(payload), ensure_ascii=False, sort_keys=True)
        request_hash = hashlib.sha256(request_json.encode()).hexdigest()
        if not key:
            return None, "", request_hash
        record = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        if record is None:
            return None, key, request_hash
        if record.request_hash != request_hash:
            raise HTTPException(409, "同一幂等键不能用于不同内容")
        return json.loads(record.response_json), key, request_hash

    def idempotency_save(
        session: Session,
        operation: str,
        key: str,
        request_hash: str,
        response: dict,
    ) -> None:
        if not key:
            return
        session.add(
            IdempotencyRecord(
                operation=operation,
                idempotency_key=key,
                request_hash=request_hash,
                response_json=json.dumps(response, ensure_ascii=False, default=str),
            )
        )
        session.commit()

    @app.get("/api/v2/health")
    def health(session: DBSession) -> dict:
        session.scalar(select(func.count()).select_from(Portfolio))
        return {
            "status": "ok",
            "database": "ok",
            "ocr": "rapidocr" if ocr.available else "manual_only",
            "market_provider": market_provider.name,
            "ai": ai_configuration_status(settings)["status"],
            "rule_version": settings.rule_config.version,
        }

    @app.get("/api/v2/portfolio")
    def get_portfolio(session: DBSession) -> dict:
        portfolio = ensure_portfolio(session, settings.rule_config.values["portfolio"]["default_budget"])
        snapshot = latest_snapshot(session, complete_only=True)
        newest = latest_snapshot(session)
        current_bucket_summary = (
            bucket_allocation(
                [{"amount": item.amount, "bucket": item.bucket} for item in snapshot.items],
                settings.rule_config.values,
            )
            if snapshot
            else {}
        )
        return {
            "id": portfolio.id,
            "name": portfolio.name,
            "capital_budget": portfolio.capital_budget,
            "updated_at": portfolio.updated_at,
            "rule_version": settings.rule_config.version,
            "buckets": settings.rule_config.values["buckets"],
            "latest_snapshot": snapshot_json(snapshot),
            "latest_draft": snapshot_json(newest) if newest and newest.completeness != "complete" else None,
            "current_bucket_summary": current_bucket_summary,
        }

    @app.put("/api/v2/portfolio")
    def update_portfolio(payload: PortfolioUpdate, session: DBSession) -> dict:
        portfolio = ensure_portfolio(session, settings.rule_config.values["portfolio"]["default_budget"])
        portfolio.name = payload.name
        portfolio.capital_budget = payload.capital_budget
        session.commit()
        return get_portfolio(session)

    @app.get("/api/v2/portfolio/snapshots")
    def list_snapshots(session: DBSession) -> list[dict]:
        rows = list(session.scalars(select(HoldingSnapshot).options(selectinload(HoldingSnapshot.items).selectinload(HoldingItem.fund)).order_by(HoldingSnapshot.as_of_date.desc(), HoldingSnapshot.id.desc()).limit(50)))
        return [snapshot_json(item) for item in rows]

    @app.post("/api/v2/portfolio/snapshots", status_code=201)
    def add_snapshot(payload: SnapshotCreate, request: Request, session: DBSession) -> dict:
        existing, key, request_hash = idempotency_lookup(session, request, "create_snapshot", payload)
        if existing is not None:
            return existing
        response = snapshot_json(create_snapshot(session, payload, settings.rule_config.values))
        idempotency_save(session, "create_snapshot", key, request_hash, response)
        return response

    @app.put("/api/v2/funds/{code}/bucket")
    def set_bucket(code: str, payload: BucketAssignmentUpdate, session: DBSession) -> dict:
        fund = session.scalar(select(Fund).where(Fund.code == code))
        if fund is None:
            raise HTTPException(404, "基金不存在")
        assignment = session.scalar(select(BucketAssignment).where(BucketAssignment.fund_id == fund.id))
        if assignment is None:
            assignment = BucketAssignment(fund_id=fund.id, bucket=payload.bucket, source="user", note=payload.note)
            session.add(assignment)
        else:
            assignment.bucket, assignment.note, assignment.assigned_at = payload.bucket, payload.note, datetime.now(UTC)
        session.commit()
        return {"fund_code": code, "bucket": assignment.bucket, "source": "user"}

    @app.get("/api/v2/funds", response_model=list[FundRead])
    def list_funds(session: DBSession, q: str = ""):
        query = select(Fund).order_by(Fund.updated_at.desc())
        if q:
            query = query.where((Fund.code.contains(q)) | (Fund.name.contains(q)))
        return list(session.scalars(query.limit(100)))

    @app.post("/api/v2/funds", response_model=FundRead, status_code=201)
    def add_fund(payload: FundEnsure, session: DBSession):
        fund = ensure_fund(session, payload.code, payload.name, payload.fund_type)
        session.commit()
        session.refresh(fund)
        return fund

    @app.get("/api/v2/funds/{code}")
    def get_fund(code: str, session: DBSession) -> dict:
        fund = session.scalar(select(Fund).where(Fund.code == code))
        if fund is None:
            raise HTTPException(404, "基金不存在")
        nav = list(session.execute(select(NavPoint.nav_date, NavPoint.cumulative_nav, NavPoint.unit_nav).where(NavPoint.fund_id == fund.id).order_by(NavPoint.nav_date.desc()).limit(400)))
        evidence = list(session.scalars(select(Evidence).where(Evidence.fund_id == fund.id).order_by(Evidence.published_at.desc()).limit(50)))
        ordered_nav = list(reversed(nav))
        cumulative_points = [(day, cumulative) for day, cumulative, _ in ordered_nav if cumulative is not None]
        performance = (
            calculate_window_metrics(cumulative_points, 252).as_dict()
            if len(cumulative_points) >= 2
            else None
        )
        return {
            "fund": fund_dict(fund),
            "nav": [{"date": day.isoformat(), "value": cumulative if cumulative is not None else unit, "total_return_quality": "ready" if cumulative is not None else "limited"} for day, cumulative, unit in ordered_nav],
            "performance": performance,
            "performance_chart": calculate_performance_chart(cumulative_points, 252),
            "evidence": [{
                "id": item.id, "title": item.title, "source_url": item.source_url,
                "published_at": item.published_at.isoformat(), "source_level": item.source_level,
                "event_type": item.event_type, "severity": item.severity, "verified": item.verified,
            } for item in evidence],
        }

    @app.post("/api/v2/funds/{code}/refresh")
    def refresh(code: str, session: DBSession) -> dict:
        try:
            fund = refresh_fund(session, market_provider, code)
            return get_fund(fund.code, session)
        except Exception as exc:
            cached = session.scalar(select(Fund).where(Fund.code == code))
            if cached is not None and cached.value_date is not None:
                cached.quality_status = "limited"
                session.commit()
                response = get_fund(code, session)
                response["cache_used"] = True
                response["warning"] = "实时刷新失败，当前展示已验证缓存；涉及质量和替代的结论已降级"
                return response
            raise HTTPException(503, "公开数据刷新失败；未使用演示数据，请检查网络或稍后重试") from exc

    @app.post("/api/v2/evidence/manual", status_code=201)
    def add_evidence(payload: EvidenceCreate, session: DBSession) -> dict:
        fund = None
        if payload.fund_code:
            fund = session.scalar(select(Fund).where(Fund.code == payload.fund_code))
            if fund is None:
                fund = ensure_fund(session, payload.fund_code)
        event_type, severity = classify_event(payload.title)
        if payload.event_type != "other":
            event_type = payload.event_type
            severity = "critical" if event_type in {"liquidation", "redemption_suspension", "contract_termination"} else "high"
        source_level = "B" if payload.evidence_kind == "news" else payload.source_level
        content_hash = hashlib.sha256(
            f"{payload.fund_code}|{payload.title}|{payload.published_at}|{payload.source_url}|{payload.content}".encode()
        ).hexdigest()
        existing = session.scalar(select(Evidence).where(Evidence.content_hash == content_hash))
        if existing:
            raise HTTPException(409, "该证据已存在")
        evidence = Evidence(
            fund_id=fund.id if fund else None, evidence_kind=payload.evidence_kind,
            title=payload.title, source_url=payload.source_url, source_level=source_level,
            published_at=payload.published_at, available_from=payload.published_at,
            content=payload.content, content_hash=content_hash, event_type=event_type,
            severity=severity, verified=payload.verified,
        )
        session.add(evidence)
        session.commit()
        session.refresh(evidence)
        return {"id": evidence.id, "event_type": evidence.event_type, "severity": evidence.severity, "verified": evidence.verified}

    def run_review_task(run_id: int) -> None:
        with database.session_factory() as task_session:
            run = task_session.get(ReviewRun, run_id)
            if run:
                try:
                    process_review(task_session, market_provider, run, settings.rule_config.values)
                except Exception as exc:  # defensive task boundary
                    run.status, run.data_quality, run.verdict = "failed", "blocked", "review"
                    run.error = f"{type(exc).__name__}: 评估任务失败"
                    run.completed_at = datetime.now(UTC)
                    task_session.commit()

    @app.post("/api/v2/reviews", status_code=202)
    def start_review(background: BackgroundTasks, session: DBSession) -> dict:
        snapshot = latest_snapshot(session, complete_only=True)
        if snapshot is None:
            raise HTTPException(409, "请先确认一份完整持仓快照")
        fingerprint = run_fingerprint(snapshot, settings.rule_config.sha256)
        existing = session.scalar(select(ReviewRun).where(ReviewRun.input_fingerprint == fingerprint, ReviewRun.status.in_(["queued", "running"])).order_by(ReviewRun.id.desc()))
        if existing:
            return {"run_id": existing.id, "status": existing.status}
        run = ReviewRun(
            snapshot_id=snapshot.id, status="queued", progress=0, verdict="review",
            data_quality="limited", as_of_date=date.today(), rule_version=settings.rule_config.version,
            rule_hash=settings.rule_config.sha256, input_fingerprint=fingerprint,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        background.add_task(run_review_task, run.id)
        return {"run_id": run.id, "status": run.status}

    @app.get("/api/v2/reviews")
    def list_reviews(session: DBSession) -> list[dict]:
        runs = list(session.scalars(select(ReviewRun).options(selectinload(ReviewRun.items).selectinload(ReviewItem.fund), selectinload(ReviewRun.items).selectinload(ReviewItem.decision)).order_by(ReviewRun.id.desc()).limit(50)))
        return [review_json(run) for run in runs]

    @app.get("/api/v2/reviews/latest")
    def latest_review(session: DBSession) -> dict | None:
        run = session.scalar(select(ReviewRun).options(selectinload(ReviewRun.items).selectinload(ReviewItem.fund), selectinload(ReviewRun.items).selectinload(ReviewItem.decision)).order_by(ReviewRun.id.desc()))
        return review_json(run) if run else None

    @app.get("/api/v2/reviews/{run_id}")
    def get_review(run_id: int, session: DBSession) -> dict:
        run = session.scalar(select(ReviewRun).options(selectinload(ReviewRun.items).selectinload(ReviewItem.fund), selectinload(ReviewRun.items).selectinload(ReviewItem.decision)).where(ReviewRun.id == run_id))
        if run is None:
            raise HTTPException(404, "评估不存在")
        return review_json(run)

    @app.post("/api/v2/review-items/{item_id}/decision")
    def decide(item_id: int, payload: ReviewDecisionCreate, request: Request, session: DBSession) -> dict:
        existing, key, request_hash = idempotency_lookup(
            session, request, f"review_decision:{item_id}", payload
        )
        if existing is not None:
            return existing
        item = session.get(ReviewItem, item_id)
        if item is None:
            raise HTTPException(404, "复核事项不存在")
        decision = session.scalar(select(ReviewDecision).where(ReviewDecision.item_id == item_id))
        if decision is None:
            decision = ReviewDecision(item_id=item_id, user_choice=payload.user_choice, note=payload.note)
            session.add(decision)
        else:
            decision.user_choice, decision.note, decision.decided_at = payload.user_choice, payload.note, datetime.now(UTC)
        item.status = {"agree": "acknowledged", "reject": "dismissed", "defer": "deferred"}[payload.user_choice]
        session.commit()
        response = {"item_id": item_id, "status": item.status, "choice": payload.user_choice}
        idempotency_save(session, f"review_decision:{item_id}", key, request_hash, response)
        return response

    @app.get("/api/v2/funds/{code}/alternatives")
    def alternatives(code: str, session: DBSession) -> list[dict]:
        fund = session.scalar(select(Fund).where(Fund.code == code))
        if fund is None:
            raise HTTPException(404, "基金不存在")
        try:
            fund = refresh_fund(session, market_provider, code)
        except Exception as exc:
            raise HTTPException(503, "当前基金最新净值或申赎状态无法复核，替代结论已阻断") from exc
        snapshot = latest_snapshot(session, complete_only=True)
        bucket = fund.default_bucket
        if snapshot:
            holding = next((item for item in snapshot.items if item.fund_id == fund.id), None)
            if holding:
                bucket = holding.bucket
        with suppress(Exception):
            prepare_peer_universe(session, market_provider, fund)
        # 已缓存同类仍可比较；生产模式绝不回退到演示数据。
        return alternatives_for(session, fund, bucket, settings.rule_config.values)

    def run_discovery_task(run_id: int) -> None:
        with database.session_factory() as task_session:
            run = task_session.get(DiscoveryRun, run_id)
            if run:
                try:
                    process_discovery(task_session, market_provider, run, settings.rule_config.values)
                except Exception as exc:  # defensive task boundary
                    run.status = "failed"
                    run.error = f"{type(exc).__name__}: 基金探索任务失败"
                    run.completed_at = datetime.now(UTC)
                    task_session.commit()

    @app.post("/api/v2/discoveries", status_code=202)
    def start_discovery(background: BackgroundTasks, session: DBSession) -> dict:
        snapshot = latest_snapshot(session, complete_only=True)
        if snapshot is None:
            raise HTTPException(409, "请先确认一份完整持仓快照")
        existing = session.scalar(
            select(DiscoveryRun)
            .where(DiscoveryRun.status.in_(["queued", "running"]))
            .order_by(DiscoveryRun.id.desc())
        )
        if existing:
            return {"run_id": existing.id, "status": existing.status}
        run = DiscoveryRun(
            snapshot_id=snapshot.id,
            status="queued",
            progress=0,
            rule_version=settings.rule_config.version,
            rule_hash=settings.rule_config.sha256,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        background.add_task(run_discovery_task, run.id)
        return {"run_id": run.id, "status": run.status}

    @app.get("/api/v2/discoveries/latest")
    def latest_discovery(session: DBSession) -> dict | None:
        run = session.scalar(select(DiscoveryRun).order_by(DiscoveryRun.id.desc()))
        return discovery_json(run) if run else None

    @app.get("/api/v2/discoveries/{run_id}")
    def get_discovery(run_id: int, session: DBSession) -> dict:
        run = session.get(DiscoveryRun, run_id)
        if run is None:
            raise HTTPException(404, "基金探索不存在")
        return discovery_json(run)

    @app.post("/api/v2/reviews/{run_id}/explain")
    async def explain(run_id: int, session: DBSession) -> dict:
        run = session.scalar(select(ReviewRun).options(selectinload(ReviewRun.items).selectinload(ReviewItem.fund), selectinload(ReviewRun.items).selectinload(ReviewItem.decision)).where(ReviewRun.id == run_id))
        if run is None:
            raise HTTPException(404, "评估不存在")
        visible_items = [item for item in run.items if item.reason_type != "band_breach"]
        ids = sorted({evidence_id for item in visible_items for evidence_id in json.loads(item.evidence_ids_json or "[]")})
        evidence_rows = list(session.scalars(select(Evidence).where(Evidence.id.in_(ids)).limit(8))) if ids else []
        pack = [{
            "evidence_id": f"ev_{item.id}", "title": item.title, "source_url": item.source_url,
            "published_at": item.published_at.isoformat(), "source_level": item.source_level,
            "content": item.content[:1600],
        } for item in evidence_rows]
        safe_review = {
            "verdict": review_json(run)["verdict"], "data_quality": run.data_quality,
            "as_of_date": run.as_of_date.isoformat(),
            "items": [{
                "reason_type": item.reason_type,
                "proposed_action": item.proposed_action,
                "title": item.title,
                "metrics": {
                    key: value
                    for key, value in json.loads(item.metric_json or "{}").items()
                    if key not in {"amount", "target_amount", "target_delta", "market_value"}
                },
            } for item in visible_items],
        }
        pack_ids = [item["evidence_id"] for item in pack]
        cached = session.scalar(
            select(AiRun)
            .where(
                AiRun.review_run_id == run.id,
                AiRun.model == settings.deepseek_model,
                AiRun.status == "ok",
                AiRun.evidence_ids_json == json.dumps(pack_ids),
                AiRun.prompt_version == AI_PROMPT_VERSION,
                AiRun.schema_version == AI_SCHEMA_VERSION,
            )
            .order_by(AiRun.id.desc())
        )
        if cached is not None:
            return {**json.loads(cached.result_json), "cached": True, "created_at": cached.created_at.isoformat()}
        result = await explain_review(settings, safe_review, pack)
        session.add(AiRun(
            review_run_id=run.id, model=settings.deepseek_model, status=result["status"],
            prompt_version=AI_PROMPT_VERSION, schema_version=AI_SCHEMA_VERSION,
            evidence_ids_json=json.dumps(pack_ids),
            result_json=json.dumps(result, ensure_ascii=False),
        ))
        session.commit()
        return result

    @app.get("/api/v2/reviews/{run_id}/explanation")
    def get_explanation(run_id: int, session: DBSession) -> dict | None:
        if session.get(ReviewRun, run_id) is None:
            raise HTTPException(404, "评估不存在")
        ai_run = session.scalar(
            select(AiRun)
            .where(
                AiRun.review_run_id == run_id,
                AiRun.prompt_version == AI_PROMPT_VERSION,
                AiRun.schema_version == AI_SCHEMA_VERSION,
            )
            .order_by(AiRun.id.desc())
        )
        if ai_run is None:
            return None
        return {
            **json.loads(ai_run.result_json or "{}"),
            "status": ai_run.status,
            "model": ai_run.model,
            "created_at": ai_run.created_at.isoformat(),
            "cached": True,
        }

    @app.get("/api/v2/data-health")
    def data_health(session: DBSession) -> dict:
        blocked = session.scalar(select(func.count()).select_from(Fund).where(Fund.quality_status == "blocked")) or 0
        limited = session.scalar(select(func.count()).select_from(Fund).where(Fund.quality_status == "limited")) or 0
        latest_fetch = session.scalar(select(func.max(ProviderSnapshot.fetched_at)))
        ai_configuration = ai_configuration_status(settings)
        return {
            "provider": market_provider.name,
            "fund_count": session.scalar(select(func.count()).select_from(Fund)) or 0,
            "blocked_funds": blocked,
            "limited_funds": limited,
            "latest_fetch": latest_fetch,
            "ocr": "ready" if ocr.available else "manual_only",
            "ai": ai_configuration["status"],
            "ai_config": ai_configuration,
        }

    @app.get("/api/v2/rule-config")
    def rule_config() -> dict:
        return {"version": settings.rule_config.version, "sha256": settings.rule_config.sha256, "rules": settings.rule_config.values}

    def require_local_settings_request(request: Request) -> None:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(403, "AI 配置只允许从本机修改")

    @app.get("/api/v2/settings/ai")
    def get_ai_settings() -> dict:
        return ai_configuration_status(settings)

    @app.put("/api/v2/settings/ai")
    def save_ai_settings(payload: AiSettingsUpdate, request: Request) -> dict:
        nonlocal settings
        require_local_settings_request(request)
        requested_keys = {"FUNDLAB_AI_ENABLED", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"}
        if payload.api_key is not None or payload.clear_api_key:
            requested_keys.add("DEEPSEEK_API_KEY")
        overridden = sorted(requested_keys.intersection(os.environ))
        if overridden:
            raise HTTPException(409, f"以下配置由启动环境覆盖，无法从页面修改：{'、'.join(overridden)}")

        key_value = None if payload.clear_api_key else payload.api_key
        updates: dict[str, str | None] = {
            "FUNDLAB_AI_ENABLED": "true" if payload.enabled else "false",
            "DEEPSEEK_BASE_URL": payload.base_url,
            "DEEPSEEK_MODEL": payload.model,
        }
        if payload.clear_api_key or payload.api_key is not None:
            updates["DEEPSEEK_API_KEY"] = key_value
        update_local_env(settings.project_root / ".env", updates)
        refreshed = Settings.from_env(settings.project_root)
        if database_url is not None:
            refreshed = replace(refreshed, database_url=database_url)
        settings = refreshed
        app.state.settings = refreshed
        return {**ai_configuration_status(settings), "message": "AI 配置已保存并即时生效"}

    @app.post("/api/v2/settings/ai/test")
    async def ai_test() -> dict:
        return await test_deepseek(settings)

    @app.get("/api/v2/exports/full")
    def export_full(session: DBSession) -> JSONResponse:
        portfolio = get_portfolio(session)
        reviews = list_reviews(session)
        funds = [fund_dict(item) for item in session.scalars(select(Fund).order_by(Fund.code))]
        response = JSONResponse(jsonable_encoder({"exported_at": datetime.now(UTC).isoformat(), "portfolio": portfolio, "funds": funds, "reviews": reviews}))
        response.headers["Content-Disposition"] = f'attachment; filename="fundlab-v2-{date.today().isoformat()}.json"'
        return response

    @app.post("/api/v2/imports", status_code=201)
    async def upload_import(session: DBSession, image: UploadFile = File(...)):
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(415, "只支持 JPG、PNG 或 WebP")
        content = await image.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "图片不能超过 12MB")
        digest = hashlib.sha256(content).hexdigest()
        existing = session.scalar(select(ImportBatch).where(ImportBatch.content_hash == digest))
        if existing:
            raise HTTPException(409, "该图片已经导入")
        suffix = ALLOWED_IMAGE_TYPES[image.content_type]
        path = settings.upload_dir / f"{digest}{suffix}"
        path.write_bytes(content)
        if Image is not None:
            try:
                with Image.open(path) as opened:
                    opened.verify()
            except Exception as exc:
                path.unlink(missing_ok=True)
                raise HTTPException(400, "图片文件损坏或格式不合法") from exc
        batch = ImportBatch(filename=image.filename or path.name, content_hash=digest, image_path=str(path), status="uploaded")
        session.add(batch)
        session.commit()
        session.refresh(batch)
        return {"id": batch.id, "filename": batch.filename, "status": batch.status, "items": []}

    @app.post("/api/v2/imports/{batch_id}/process")
    def process_import(batch_id: int, session: DBSession) -> dict:
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            raise HTTPException(404, "导入批次不存在")
        try:
            text, scores, boxes = ocr.extract(Path(batch.image_path))
            local_catalog = [(fund.code, fund.name) for fund in session.scalars(select(Fund))]
            resolved = match_fund_catalog(text, local_catalog)
            if len(resolved) < 2:
                with suppress(Exception):
                    public_resolved = market_provider.resolve_fund_names(text, limit=30)
                    by_code = {item[0]: item for item in resolved}
                    for item in public_resolved:
                        if item[0] not in by_code or item[2] > by_code[item[0]][2]:
                            by_code[item[0]] = item
                    resolved = list(by_code.values())
            page_type, drafts = parse_ocr_text(text, resolved)
            batch.raw_text = text
            batch.status = "needs_review"
            current = latest_snapshot(session, complete_only=True)
            current_buckets = {item.fund.code: item.bucket for item in current.items} if current else {}
            for old in list(batch.items):
                session.delete(old)
            for draft in drafts:
                if draft.kind != "holding":
                    continue
                fund = ensure_fund(session, draft.fund_code, draft.fund_name) if draft.fund_code else None
                bucket = current_buckets.get(draft.fund_code, fund.default_bucket if fund else "satellite")
                session.add(ImportItem(
                    batch_id=batch.id, fund_code=draft.fund_code, fund_name=draft.fund_name,
                    amount=draft.amount, displayed_profit=draft.displayed_profit,
                    bucket=bucket,
                    confidence=min(draft.confidence, sum(scores) / len(scores)) if scores else 0,
                    raw_text=text, bbox_json=json.dumps(boxes, ensure_ascii=False),
                    issues=(draft.issues or f"页面类型：{page_type}") + f"；已按产品类型自动归入{settings.rule_config.values['buckets'][bucket]['label']}，可人工覆盖",
                ))
            session.commit()
            session.refresh(batch, attribute_names=["items"])
        except Exception as exc:
            batch.status, batch.error = "failed", "OCR 处理失败，可改用手工录入"
            session.commit()
            raise HTTPException(500, batch.error) from exc
        return import_json(batch)

    @app.get("/api/v2/imports")
    def list_imports(session: DBSession) -> list[dict]:
        rows = list(session.scalars(select(ImportBatch).options(selectinload(ImportBatch.items)).order_by(ImportBatch.id.desc()).limit(50)))
        return [import_json(item) for item in rows]

    @app.post("/api/v2/imports/{batch_id}/confirm", status_code=201)
    def confirm_import(batch_id: int, payload: ImportConfirm, session: DBSession) -> dict:
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            raise HTTPException(404, "导入批次不存在")
        snapshot_payload = SnapshotCreate(
            as_of_date=payload.as_of_date, completeness=payload.completeness, source="ocr",
            note=f"来自导入批次 {batch.id}",
            items=[{
                "fund_code": item.fund_code,
                "fund_name": item.fund_name,
                "amount": item.amount,
                "displayed_profit": item.displayed_profit,
                "bucket": item.bucket,
            } for item in payload.items],
        )
        snapshot = create_snapshot(session, snapshot_payload, settings.rule_config.values)
        corrections = {item.fund_code: item for item in payload.items}
        for draft in batch.items:
            correction = corrections.get(draft.fund_code)
            if correction is None:
                continue
            draft.confirmed = True
            draft.correction_json = correction.model_dump_json()
        batch.status = "confirmed" if payload.completeness == "complete" else "partially_confirmed"
        session.commit()
        return snapshot_json(snapshot)

    def import_json(batch: ImportBatch) -> dict:
        return {
            "id": batch.id, "filename": batch.filename, "status": batch.status,
            "raw_text": batch.raw_text, "error": batch.error, "created_at": batch.created_at.isoformat(),
            "page_type": classify_page(batch.raw_text) if batch.raw_text else "unprocessed",
            "items": [{
                "id": item.id, "fund_code": item.fund_code, "fund_name": item.fund_name,
                "amount": item.amount, "displayed_profit": item.displayed_profit,
                "bucket": item.bucket, "confidence": item.confidence,
                "issues": item.issues, "confirmed": item.confirmed,
            } for item in batch.items],
        }

    frontend_dist = settings.project_root / "frontend" / "dist"
    if frontend_dist.exists():
        assets = frontend_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            target = frontend_dist / full_path
            if full_path and target.is_file():
                return FileResponse(target)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
