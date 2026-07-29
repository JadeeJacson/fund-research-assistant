import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from PIL import Image
except ImportError:  # pragma: no cover - 正式依赖中包含 Pillow
    Image = None

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .ai import explain_report, test_deepseek
from .analytics import calculate_metrics
from .config import Settings
from .database import Database
from .decision import DecisionContext, build_decision
from .models import (
    AnalysisReport,
    Candidate,
    Evidence,
    Holding,
    ImportBatch,
    ImportItem,
    NavPoint,
    Transaction,
    TriggerRule,
)
from .ocr import OCRService, parse_ocr_text
from .providers import KNOWN_FUNDS, ProviderChain
from .schemas import (
    CandidateCreate,
    CandidateRead,
    EvidenceCreate,
    EvidenceRead,
    HoldingCreate,
    HoldingRead,
    ImportBatchRead,
    ImportItemRead,
    ImportItemUpdate,
    ReportRequest,
    TransactionCreate,
    TransactionRead,
    TriggerCreate,
    TriggerRead,
)

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def transaction_fingerprint(payload: TransactionCreate) -> str:
    normalized = "|".join(
        [
            payload.fund_code,
            payload.action,
            payload.trade_time.isoformat(),
            str(payload.amount),
            str(payload.shares),
            payload.source,
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _operator_matches(value: float, operator: str, threshold: float) -> bool:
    return {
        "<": value < threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        ">=": value >= threshold,
    }[operator]


def create_app(
    *,
    database_url: str | None = None,
    project_root: Path | None = None,
) -> FastAPI:
    settings = Settings.from_env(project_root)
    if database_url is not None:
        settings = Settings(
            project_root=settings.project_root,
            database_url=database_url,
            upload_dir=settings.upload_dir,
            risk_tolerance=settings.risk_tolerance,
            ai_enabled=settings.ai_enabled,
            deepseek_api_key=settings.deepseek_api_key,
            deepseek_base_url=settings.deepseek_base_url,
            deepseek_model=settings.deepseek_model,
            market_provider=settings.market_provider,
            keep_uploads=settings.keep_uploads,
        )
    database = Database(settings.database_url)
    database.create_all()
    provider = ProviderChain(settings.market_provider)
    ocr_service = OCRService()

    app = FastAPI(
        title="个人基金研究助手 API",
        version="1.0.0-mvp",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.database = database
    app.state.provider = provider
    app.state.ocr = ocr_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "输入内容未通过校验",
                    "details": exc.errors(),
                }
            },
        )

    def session_dependency():
        yield from database.session()

    DBSession = Annotated[Session, Depends(session_dependency)]

    @app.get("/api/v1/health")
    def health(session: DBSession) -> dict:
        session.execute(select(func.count()).select_from(Candidate)).scalar_one()
        return {
            "status": "ok",
            "database": "ok",
            "ocr": "rapidocr" if ocr_service.available else "manual_review",
            "market_provider": provider.status,
            "ai": "deepseek" if settings.ai_enabled else "mock",
            "risk_tolerance": settings.risk_tolerance,
        }

    @app.get("/api/v1/dashboard")
    def dashboard(session: DBSession) -> dict:
        latest_day = session.scalar(select(func.max(Holding.snapshot_date)))
        holdings = (
            list(session.scalars(select(Holding).where(Holding.snapshot_date == latest_day)))
            if latest_day
            else []
        )
        total = sum(item.amount for item in holdings)
        return {
            "candidate_count": session.scalar(select(func.count()).select_from(Candidate)) or 0,
            "holding_count": len(holdings),
            "portfolio_amount": round(total, 2),
            "pending_imports": session.scalar(
                select(func.count())
                .select_from(ImportBatch)
                .where(ImportBatch.status == "needs_review")
            )
            or 0,
            "latest_snapshot_date": latest_day,
            "risk_tolerance": settings.risk_tolerance,
        }

    @app.get("/api/v1/candidates", response_model=list[CandidateRead])
    def list_candidates(session: DBSession):
        return list(session.scalars(select(Candidate).order_by(Candidate.created_at.desc())))

    @app.post("/api/v1/candidates", response_model=CandidateRead, status_code=201)
    def create_candidate(payload: CandidateCreate, session: DBSession):
        existing = session.scalar(select(Candidate).where(Candidate.fund_code == payload.fund_code))
        if existing:
            raise HTTPException(status_code=409, detail="该基金已在候选列表中")
        known = KNOWN_FUNDS.get(payload.fund_code)
        candidate = Candidate(
            fund_code=payload.fund_code,
            fund_name=payload.fund_name or (known[0] if known else f"待刷新基金 {payload.fund_code}"),
            share_class=payload.share_class or (known[2] if known else ""),
            fund_type=payload.fund_type if payload.fund_type != "unknown" else (known[1] if known else "unknown"),
            note=payload.note,
            planned_amount=payload.planned_amount,
        )
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        return candidate

    @app.delete("/api/v1/candidates/{candidate_id}", status_code=204)
    def delete_candidate(candidate_id: int, session: DBSession):
        candidate = session.get(Candidate, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选基金不存在")
        session.execute(delete(NavPoint).where(NavPoint.candidate_id == candidate_id))
        session.execute(delete(AnalysisReport).where(AnalysisReport.candidate_id == candidate_id))
        session.execute(delete(Evidence).where(Evidence.candidate_id == candidate_id))
        session.execute(delete(TriggerRule).where(TriggerRule.candidate_id == candidate_id))
        session.delete(candidate)
        session.commit()

    @app.post("/api/v1/candidates/{candidate_id}/refresh", response_model=CandidateRead)
    def refresh_candidate(candidate_id: int, session: DBSession):
        candidate = session.get(Candidate, candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选基金不存在")
        try:
            data = provider.load(candidate.fund_code)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="公开数据刷新失败，请稍后重试") from exc
        candidate.fund_name = data.fund_name
        candidate.fund_type = data.fund_type
        candidate.share_class = data.share_class
        candidate.latest_nav = data.nav_points[-1][1]
        candidate.nav_date = data.nav_points[-1][0]
        candidate.data_source = data.source
        candidate.refreshed_at = datetime.now(UTC)
        session.execute(delete(NavPoint).where(NavPoint.candidate_id == candidate.id))
        session.add_all(
            [
                NavPoint(
                    candidate_id=candidate.id,
                    nav_date=point_date,
                    nav=nav,
                    source=data.source,
                )
                for point_date, nav in data.nav_points[-1500:]
            ]
        )
        session.commit()
        session.refresh(candidate)
        return candidate

    @app.post("/api/v1/reports")
    def create_report(payload: ReportRequest, session: DBSession) -> dict:
        candidate = session.get(Candidate, payload.candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="候选基金不存在")
        points = list(
            session.execute(
                select(NavPoint.nav_date, NavPoint.nav)
                .where(NavPoint.candidate_id == candidate.id)
                .order_by(NavPoint.nav_date)
            ).all()
        )
        if not points:
            data = provider.load(candidate.fund_code)
            candidate.fund_name = data.fund_name
            candidate.fund_type = data.fund_type
            candidate.share_class = data.share_class
            candidate.latest_nav = data.nav_points[-1][1]
            candidate.nav_date = data.nav_points[-1][0]
            candidate.data_source = data.source
            candidate.refreshed_at = datetime.now(UTC)
            session.add_all(
                [
                    NavPoint(
                        candidate_id=candidate.id,
                        nav_date=point_date,
                        nav=nav,
                        source=data.source,
                    )
                    for point_date, nav in data.nav_points[-1500:]
                ]
            )
            session.flush()
            points = data.nav_points
        metrics = calculate_metrics(points)
        latest_day = session.scalar(select(func.max(Holding.snapshot_date)))
        holdings = (
            list(session.scalars(select(Holding).where(Holding.snapshot_date == latest_day)))
            if latest_day
            else []
        )
        total = sum(item.amount for item in holdings)
        current = sum(item.amount for item in holdings if item.fund_code == candidate.fund_code)
        current_weight = current / total if total else 0.0
        decision = build_decision(
            metrics,
            DecisionContext(
                fund_name=candidate.fund_name,
                fund_type=candidate.fund_type,
                horizon=payload.horizon,
                current_weight=current_weight,
                data_source=candidate.data_source,
                risk_tolerance=settings.risk_tolerance,
            ),
        )
        result = {
            "candidate": CandidateRead.model_validate(candidate).model_dump(mode="json"),
            "horizon": payload.horizon,
            "as_of_date": metrics.as_of_date.isoformat(),
            "metrics": metrics.as_dict(),
            "current_weight": current_weight,
            "decision": decision,
            "evidence": [
                EvidenceRead.model_validate(item).model_dump(mode="json")
                for item in session.scalars(
                    select(Evidence)
                    .where(Evidence.candidate_id == candidate.id)
                    .order_by(Evidence.published_at.desc())
                )
            ],
            "ai_explanation": {
                "status": "not_generated",
                "message": "MVP 先展示确定性结论；AI 仅在设置启用并提供 Evidence Pack 后解释",
            },
        }
        report = AnalysisReport(
            candidate_id=candidate.id,
            horizon=payload.horizon,
            result_json=json.dumps(result, ensure_ascii=False),
        )
        session.add(report)
        session.commit()
        result["report_id"] = report.id
        return result

    @app.get("/api/v1/reports/{report_id}")
    def get_report(report_id: int, session: DBSession):
        report = session.get(AnalysisReport, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="研究报告不存在")
        result = json.loads(report.result_json)
        result["report_id"] = report.id
        return result

    @app.post("/api/v1/reports/{report_id}/explain")
    async def explain(report_id: int, session: DBSession):
        report = session.get(AnalysisReport, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="研究报告不存在")
        result = json.loads(report.result_json)
        evidence_rows = list(
            session.scalars(
                select(Evidence)
                .where(Evidence.candidate_id == report.candidate_id)
                .order_by(Evidence.published_at.desc())
                .limit(20)
            )
        )
        evidence_pack = [
            {
                "evidence_id": f"ev_{item.id}",
                "title": item.title,
                "source_url": item.source_url,
                "published_at": item.published_at.isoformat(),
                "trust_level": item.trust_level,
                "content": item.content,
            }
            for item in evidence_rows
        ]
        safe_report = {
            "candidate": result["candidate"],
            "horizon": result["horizon"],
            "as_of_date": result["as_of_date"],
            "metrics": result["metrics"],
            "decision": result["decision"],
        }
        result["evidence"] = evidence_pack
        result["ai_explanation"] = await explain_report(settings, safe_report, evidence_pack)
        report.result_json = json.dumps(result, ensure_ascii=False)
        session.commit()
        result["report_id"] = report.id
        return result

    @app.get("/api/v1/evidence", response_model=list[EvidenceRead])
    def list_evidence(candidate_id: int, session: DBSession):
        return list(
            session.scalars(
                select(Evidence)
                .where(Evidence.candidate_id == candidate_id)
                .order_by(Evidence.published_at.desc())
            )
        )

    @app.post("/api/v1/evidence", response_model=EvidenceRead, status_code=201)
    def create_evidence(payload: EvidenceCreate, session: DBSession):
        if not session.get(Candidate, payload.candidate_id):
            raise HTTPException(status_code=404, detail="候选基金不存在")
        digest = hashlib.sha256(
            f"{payload.source_url}|{payload.published_at}|{payload.content}".encode()
        ).hexdigest()
        existing = session.scalar(
            select(Evidence).where(
                Evidence.candidate_id == payload.candidate_id,
                Evidence.content_hash == digest,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="该证据已存在")
        evidence = Evidence(**payload.model_dump(), content_hash=digest)
        session.add(evidence)
        session.commit()
        session.refresh(evidence)
        return evidence

    @app.delete("/api/v1/evidence/{evidence_id}", status_code=204)
    def delete_evidence(evidence_id: int, session: DBSession):
        evidence = session.get(Evidence, evidence_id)
        if not evidence:
            raise HTTPException(status_code=404, detail="证据不存在")
        session.delete(evidence)
        session.commit()

    @app.get("/api/v1/holdings", response_model=list[HoldingRead])
    def list_holdings(session: DBSession):
        return list(
            session.scalars(
                select(Holding).order_by(Holding.snapshot_date.desc(), Holding.created_at.desc())
            )
        )

    @app.post("/api/v1/holdings", response_model=HoldingRead, status_code=201)
    def create_holding(payload: HoldingCreate, session: DBSession):
        holding = Holding(**payload.model_dump())
        session.add(holding)
        session.commit()
        session.refresh(holding)
        return holding

    @app.delete("/api/v1/holdings/{holding_id}", status_code=204)
    def delete_holding(holding_id: int, session: DBSession):
        holding = session.get(Holding, holding_id)
        if not holding:
            raise HTTPException(status_code=404, detail="持仓不存在")
        session.delete(holding)
        session.commit()

    @app.get("/api/v1/transactions", response_model=list[TransactionRead])
    def list_transactions(session: DBSession):
        return list(session.scalars(select(Transaction).order_by(Transaction.trade_time.desc())))

    @app.post("/api/v1/transactions", response_model=TransactionRead, status_code=201)
    def create_transaction(payload: TransactionCreate, session: DBSession):
        transaction = Transaction(
            **payload.model_dump(),
            fingerprint=transaction_fingerprint(payload),
        )
        session.add(transaction)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="该交易记录已存在") from exc
        session.refresh(transaction)
        return transaction

    @app.delete("/api/v1/transactions/{transaction_id}", status_code=204)
    def delete_transaction(transaction_id: int, session: DBSession):
        transaction = session.get(Transaction, transaction_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="交易不存在")
        session.delete(transaction)
        session.commit()

    @app.post("/api/v1/imports", response_model=ImportBatchRead, status_code=201)
    async def create_import(
        session: DBSession,
        image: Annotated[UploadFile, File()],
    ):
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="只支持 JPG、PNG 或 WebP 图片")
        content = await image.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="单张图片不能超过 12 MB")
        if Image is not None:
            try:
                with Image.open(io.BytesIO(content)) as decoded:
                    decoded.verify()
                    width, height = decoded.size
                if width * height > 40_000_000:
                    raise HTTPException(status_code=413, detail="图片像素过大")
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=422, detail="图片内容无法安全解码") from exc
        content_hash = hashlib.sha256(content).hexdigest()
        existing = session.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.items))
            .where(ImportBatch.content_hash == content_hash)
        )
        if existing:
            raise HTTPException(status_code=409, detail=f"该图片已在导入批次 #{existing.id} 中")
        suffix = ALLOWED_IMAGE_TYPES[image.content_type]
        destination = settings.upload_dir / f"{content_hash}{suffix}"
        destination.write_bytes(content)
        raw_text, scores = ocr_service.extract(destination)
        page_type, drafts = parse_ocr_text(raw_text)
        average_score = sum(scores) / len(scores) if scores else 0.0
        batch = ImportBatch(
            filename=Path(image.filename or f"upload{suffix}").name,
            content_hash=content_hash,
            image_path=str(destination),
            page_type=page_type,
            raw_text=raw_text,
            status="needs_review",
            error="" if ocr_service.available else "RapidOCR 未安装，请人工填写草稿字段",
        )
        for draft in drafts:
            batch.items.append(
                ImportItem(
                    kind=draft.kind,
                    fund_code=draft.fund_code,
                    fund_name=draft.fund_name,
                    action=draft.action,
                    amount=draft.amount,
                    shares=draft.shares,
                    event_time=draft.event_time,
                    confidence=min(draft.confidence, average_score or draft.confidence),
                    issues=draft.issues,
                )
            )
        session.add(batch)
        session.commit()
        return session.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.items))
            .where(ImportBatch.id == batch.id)
        )

    @app.get("/api/v1/imports", response_model=list[ImportBatchRead])
    def list_imports(session: DBSession):
        return list(
            session.scalars(
                select(ImportBatch)
                .options(selectinload(ImportBatch.items))
                .order_by(ImportBatch.created_at.desc())
            ).unique()
        )

    @app.get("/api/v1/imports/{batch_id}", response_model=ImportBatchRead)
    def get_import(batch_id: int, session: DBSession):
        batch = session.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.items))
            .where(ImportBatch.id == batch_id)
        )
        if not batch:
            raise HTTPException(status_code=404, detail="导入批次不存在")
        return batch

    @app.put("/api/v1/import-items/{item_id}", response_model=ImportItemRead)
    def update_import_item(item_id: int, payload: ImportItemUpdate, session: DBSession):
        item = session.get(ImportItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="导入草稿不存在")
        if item.confirmed:
            raise HTTPException(status_code=409, detail="已确认草稿不能直接修改")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        item.confidence = 1.0
        item.issues = ""
        session.commit()
        session.refresh(item)
        return item

    @app.post("/api/v1/imports/{batch_id}/confirm", response_model=ImportBatchRead)
    def confirm_import(batch_id: int, session: DBSession):
        batch = session.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.items))
            .where(ImportBatch.id == batch_id)
        )
        if not batch:
            raise HTTPException(status_code=404, detail="导入批次不存在")
        pending = [item for item in batch.items if not item.confirmed]
        if not pending:
            raise HTTPException(status_code=409, detail="该批次没有待确认记录")
        confirmed_count = 0
        for item in pending:
            if not item.fund_code or not item.fund_name:
                item.issues = "缺少基金代码或名称，未写入正式数据"
                continue
            if item.kind == "candidate":
                existing = session.scalar(
                    select(Candidate).where(Candidate.fund_code == item.fund_code)
                )
                if not existing:
                    known = KNOWN_FUNDS.get(item.fund_code)
                    session.add(
                        Candidate(
                            fund_code=item.fund_code,
                            fund_name=item.fund_name,
                            share_class=known[2] if known else "",
                            fund_type=known[1] if known else "unknown",
                            data_source="支付宝截图（已确认）",
                        )
                    )
            elif item.kind == "holding":
                if item.amount is None:
                    item.issues = "缺少持仓金额，未写入正式数据"
                    continue
                session.add(
                    Holding(
                        fund_code=item.fund_code,
                        fund_name=item.fund_name,
                        amount=item.amount,
                        snapshot_date=(item.event_time or datetime.now(UTC)).date(),
                        source=f"截图导入批次 #{batch.id}",
                    )
                )
            elif item.kind == "transaction":
                if item.event_time is None or (item.amount is None and item.shares is None):
                    item.issues = "缺少交易时间、金额或份额，未写入正式数据"
                    continue
                payload = TransactionCreate(
                    fund_code=item.fund_code,
                    fund_name=item.fund_name,
                    action=item.action or "buy",
                    amount=item.amount,
                    shares=item.shares,
                    trade_time=item.event_time,
                    source=f"截图导入批次 #{batch.id}",
                )
                fingerprint = transaction_fingerprint(payload)
                if not session.scalar(
                    select(Transaction).where(Transaction.fingerprint == fingerprint)
                ):
                    session.add(Transaction(**payload.model_dump(), fingerprint=fingerprint))
            item.confirmed = True
            confirmed_count += 1
        if confirmed_count == 0:
            session.commit()
            raise HTTPException(status_code=422, detail="没有可确认记录，请先修正高亮字段")
        batch.status = "confirmed" if all(item.confirmed for item in batch.items) else "partially_confirmed"
        if not settings.keep_uploads and batch.image_path:
            image_path = Path(batch.image_path)
            if image_path.is_file():
                image_path.unlink()
            batch.image_path = ""
        session.commit()
        return session.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.items))
            .where(ImportBatch.id == batch.id)
        )

    @app.delete("/api/v1/imports/{batch_id}", status_code=204)
    def delete_import(batch_id: int, session: DBSession):
        batch = session.get(ImportBatch, batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="导入批次不存在")
        image_path = Path(batch.image_path) if batch.image_path else None
        session.delete(batch)
        session.commit()
        if image_path and image_path.is_file():
            image_path.unlink()

    @app.get("/api/v1/triggers", response_model=list[TriggerRead])
    def list_triggers(session: DBSession):
        return list(session.scalars(select(TriggerRule).order_by(TriggerRule.id.desc())))

    @app.post("/api/v1/triggers", response_model=TriggerRead, status_code=201)
    def create_trigger(payload: TriggerCreate, session: DBSession):
        if not session.get(Candidate, payload.candidate_id):
            raise HTTPException(status_code=404, detail="候选基金不存在")
        trigger = TriggerRule(**payload.model_dump())
        session.add(trigger)
        session.commit()
        session.refresh(trigger)
        return trigger

    @app.delete("/api/v1/triggers/{trigger_id}", status_code=204)
    def delete_trigger(trigger_id: int, session: DBSession):
        trigger = session.get(TriggerRule, trigger_id)
        if not trigger:
            raise HTTPException(status_code=404, detail="触发器不存在")
        session.delete(trigger)
        session.commit()

    @app.post("/api/v1/triggers/check", response_model=list[TriggerRead])
    def check_triggers(session: DBSession):
        triggers = list(session.scalars(select(TriggerRule).where(TriggerRule.enabled.is_(True))))
        for trigger in triggers:
            candidate = session.get(Candidate, trigger.candidate_id)
            points = list(
                session.execute(
                    select(NavPoint.nav_date, NavPoint.nav)
                    .where(NavPoint.candidate_id == trigger.candidate_id)
                    .order_by(NavPoint.nav_date)
                ).all()
            )
            if not candidate or not points:
                trigger.last_value = None
                trigger.last_matched = False
                trigger.checked_at = datetime.now(UTC)
                continue
            metrics = calculate_metrics(points)
            values = {
                "latest_nav": candidate.latest_nav,
                "drawdown": metrics.max_drawdown,
                "annualized_return": metrics.annualized_return,
                "volatility": metrics.volatility,
            }
            value = values[trigger.metric]
            trigger.last_value = value
            trigger.last_matched = (
                _operator_matches(value, trigger.operator, trigger.threshold)
                if value is not None
                else False
            )
            trigger.checked_at = datetime.now(UTC)
        session.commit()
        return triggers

    @app.get("/api/v1/settings")
    def get_settings() -> dict:
        return {
            "risk_tolerance": settings.risk_tolerance,
            "market_provider": provider.status,
            "ocr": "rapidocr" if ocr_service.available else "manual_review",
            "ai_enabled": settings.ai_enabled,
            "ai_model": settings.deepseek_model or "未配置",
            "keep_uploads": settings.keep_uploads,
        }

    @app.get("/api/v1/exports/full")
    def export_full(session: DBSession):
        payload = {
            "exported_at": datetime.now(UTC),
            "schema": "fundlab-mvp-export-v1",
            "candidates": [
                CandidateRead.model_validate(item).model_dump(mode="json")
                for item in session.scalars(select(Candidate).order_by(Candidate.id))
            ],
            "holdings": [
                HoldingRead.model_validate(item).model_dump(mode="json")
                for item in session.scalars(select(Holding).order_by(Holding.id))
            ],
            "transactions": [
                TransactionRead.model_validate(item).model_dump(mode="json")
                for item in session.scalars(select(Transaction).order_by(Transaction.id))
            ],
            "evidence": [
                EvidenceRead.model_validate(item).model_dump(mode="json")
                for item in session.scalars(select(Evidence).order_by(Evidence.id))
            ],
            "triggers": [
                TriggerRead.model_validate(item).model_dump(mode="json")
                for item in session.scalars(select(TriggerRule).order_by(TriggerRule.id))
            ],
        }
        filename = f"fundlab-export-{date.today().isoformat()}.json"
        return JSONResponse(
            content=jsonable_encoder(payload),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/v1/settings/ai/test")
    async def ai_test() -> dict:
        return await test_deepseek(settings)

    frontend_dist = settings.project_root / "frontend" / "dist"
    if frontend_dist.exists():
        assets = frontend_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend(full_path: str):
            candidate_path = (frontend_dist / full_path).resolve()
            if (
                full_path
                and candidate_path.is_relative_to(frontend_dist.resolve())
                and candidate_path.is_file()
            ):
                return FileResponse(candidate_path)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
