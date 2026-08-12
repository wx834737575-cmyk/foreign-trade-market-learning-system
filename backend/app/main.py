from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .metrics import scissors_gap
from .ingestion.cfets_usdcny import import_cfets_usdcny
from .ingestion.nbs_core_monthly import import_nbs_core_monthly
from .ingestion.nbs_pmi import import_nbs_pmi
from .ingestion.pboc_money_supply import import_pboc_money_supply
from .ingestion.sse_freight import import_sse_freight
from .models import AnalysisNote, BusinessChannel, Dataset, Observation, RawArtifact, ReleaseCalendar, Source, UpdateRun
from .seed import seed_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class NoteInput(BaseModel):
    period: date
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    confidence: str = Field(default="medium", pattern="^(low|medium|high)$")


def _latest_map(db: Session) -> dict[str, Observation]:
    observations = db.scalars(
        select(Observation)
        .options(joinedload(Observation.dataset).joinedload(Dataset.source))
        .where(Observation.is_current.is_(True))
        .order_by(Observation.period.desc(), Observation.vintage.desc())
    ).all()
    result: dict[str, Observation] = {}
    for item in observations:
        result.setdefault(item.dataset.code, item)
    return result


def _serialize_observation(item: Observation) -> dict:
    return {
        "code": item.dataset.code,
        "name": item.dataset.name,
        "value": float(item.value),
        "unit": item.unit,
        "period": item.period.isoformat(),
        "publishedAt": item.published_at.isoformat() if item.published_at else None,
        "qualityStatus": item.quality_status,
        "source": {
            "name": item.dataset.source.name,
            "url": item.dataset.source.verification_url or item.dataset.source.homepage_url,
        },
        "note": item.note,
    }


def _serialize_note(item: AnalysisNote) -> dict:
    return {
        "id": item.id,
        "period": item.period.isoformat(),
        "title": item.title,
        "content": item.content,
        "confidence": item.confidence,
        "outcome": item.outcome,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": settings.app_version, "demoMode": settings.demo_mode}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    latest = _latest_map(db)
    cards = [_serialize_observation(item) for item in latest.values()]
    m1 = latest.get("CN_M1_YOY")
    m2 = latest.get("CN_M2_YOY")
    fx = latest.get("CN_USDCNY_CENTRAL_PARITY")
    scfi = latest.get("SCFI_COMPOSITE")
    ccfi = latest.get("CCFI_COMPOSITE")
    money_data_verified = bool(m1 and m2 and m1.quality_status == "verified" and m2.quality_status == "verified")
    gap = None
    if m1 and m2:
        gap = float(scissors_gap(Decimal(m1.value), Decimal(m2.value)))
    trend_codes = (
        "CN_MANUFACTURING_PMI",
        "CN_M1_YOY",
        "CN_M2_YOY",
        "CN_USDCNY_CENTRAL_PARITY",
        "SCFI_COMPOSITE",
        "CCFI_COMPOSITE",
        "CN_CPI_YOY",
        "CN_PPI_YOY",
        "CN_INDUSTRIAL_VALUE_ADDED_YOY",
        "CN_RETAIL_SALES_YOY",
    )
    trends: dict[str, list[dict]] = {}
    for code in trend_codes:
        dataset = db.scalar(select(Dataset).where(Dataset.code == code))
        if dataset is None:
            trends[code] = []
            continue
        history = db.scalars(
            select(Observation)
            .where(
                Observation.dataset_id == dataset.id,
                Observation.is_current.is_(True),
                Observation.quality_status == "verified",
            )
            .order_by(Observation.period)
        ).all()
        trends[code] = [
            {"period": item.period.isoformat(), "value": float(item.value), "qualityStatus": item.quality_status}
            for item in history
        ]
    verified_count = sum(item.quality_status == "verified" for item in latest.values())
    return {
        "asOf": "2026-07-20T00:00:00+08:00",
        "demoMode": settings.demo_mode,
        "dataStatus": f"{verified_count}项官方指标已核验，未核验数据不参与判断",
        "environment": [
            {"name": "国内资金环境", "status": "规则待定" if money_data_verified else "待核验", "tone": "neutral", "summary": "人民银行当期数据已核验，环境判断规则仍待制定。" if money_data_verified else "人民银行纵向样板正在建设。"},
            {"name": "外贸景气度", "status": "待首份导入", "tone": "neutral", "summary": "海关官方文件链路已配置，等待真实导出样本完成解析适配。"},
            {"name": "汇率环境", "status": "已接入" if fx and fx.quality_status == "verified" else "待核验", "tone": "positive" if fx and fx.quality_status == "verified" else "warning", "summary": f"USD/CNY中间价 {float(fx.value):.4f}（{fx.period:%Y-%m-%d}），用于报价汇率参考。" if fx and fx.quality_status == "verified" else "中国货币网官方接口已经配置。"},
            {"name": "航运环境", "status": "学习参考" if scfi and ccfi else "待核验", "tone": "neutral", "summary": f"SCFI {float(scfi.value):.2f}、CCFI {float(ccfi.value):.2f}（{max(scfi.period, ccfi.period):%Y-%m-%d}）；仅限本地个人学习。" if scfi and ccfi else "SCFI、CCFI官方最新页已经配置。"},
            {"name": "股票市场环境", "status": "学习模式", "tone": "positive", "summary": "只呈现证据和边界，不荐股。"},
        ],
        "indicators": cards,
        "derived": {"m1M2Gap": gap, "gapUnit": "个百分点"},
        "trends": trends,
    }


@app.get("/api/indicators")
def indicators(db: Session = Depends(get_db)) -> list[dict]:
    return [_serialize_observation(item) for item in _latest_map(db).values()]


@app.get("/api/indicators/{code}")
def indicator_detail(code: str, db: Session = Depends(get_db)) -> dict:
    dataset = db.scalar(select(Dataset).options(joinedload(Dataset.source)).where(Dataset.code == code))
    if dataset is None:
        raise HTTPException(status_code=404, detail="指标不存在")
    history = db.scalars(
        select(Observation)
        .where(Observation.dataset_id == dataset.id)
        .order_by(Observation.period, Observation.vintage)
    ).all()
    return {
        "code": dataset.code,
        "name": dataset.name,
        "frequency": dataset.frequency,
        "unit": dataset.unit,
        "methodology": dataset.methodology,
        "source": {"name": dataset.source.name, "url": dataset.source.verification_url},
        "history": [
            {
                "period": item.period.isoformat(),
                "value": float(item.value),
                "vintage": item.vintage,
                "qualityStatus": item.quality_status,
            }
            for item in history
        ],
    }


@app.get("/api/sources")
def sources(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(Source).order_by(Source.id)).all()
    result = []
    for item in items:
        latest_artifact = db.scalar(
            select(RawArtifact)
            .where(RawArtifact.source_id == item.id, RawArtifact.quality_status == "verified")
            .order_by(RawArtifact.fetched_at.desc())
        )
        result.append({
            "code": item.code,
            "name": item.name,
            "url": item.verification_url or item.homepage_url,
            "authorityLevel": item.authority_level,
            "acquisitionMode": item.acquisition_mode,
            "notes": item.notes,
            "evidence": None if latest_artifact is None else {
                "sha256": latest_artifact.sha256,
                "qualityStatus": latest_artifact.quality_status,
                "fetchedAt": latest_artifact.fetched_at.isoformat(),
                "parserVersion": latest_artifact.parser_version,
            },
        })
    return result


@app.get("/api/evidence")
def evidence(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(RawArtifact).order_by(RawArtifact.fetched_at.desc())).all()
    return [
        {
            "sha256": item.sha256,
            "sourceUrl": item.source_url,
            "contentType": item.content_type,
            "fetchedAt": item.fetched_at.isoformat(),
            "httpStatus": item.http_status,
            "parserVersion": item.parser_version,
            "qualityStatus": item.quality_status,
        }
        for item in items
    ]


@app.get("/api/calendar")
def release_calendar(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(ReleaseCalendar).order_by(ReleaseCalendar.expected_from)).all()
    return [
        {
            "datasetCode": item.dataset_code,
            "period": item.statistical_period.isoformat(),
            "expectedFrom": item.expected_from.isoformat() if item.expected_from else None,
            "expectedTo": item.expected_to.isoformat() if item.expected_to else None,
            "status": item.status,
            "actualReleaseAt": item.actual_release_at.isoformat() if item.actual_release_at else None,
        }
        for item in items
    ]


@app.post("/api/updates/check")
def check_updates(db: Session = Depends(get_db)) -> dict:
    jobs = [
        ("PBOC", import_pboc_money_supply),
        ("NBS", import_nbs_pmi),
        ("NBS_CORE", import_nbs_core_monthly),
        ("CFETS", import_cfets_usdcny),
        ("SSE", import_sse_freight),
    ]
    results = []
    for source_code, importer in jobs:
        run = UpdateRun(source_code=source_code, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)
        try:
            imported = importer(db)
            run.status = "success"
            run.message = f"新增 {imported.imported}，跳过 {imported.skipped}；证据 {imported.artifact_sha256[:12]}"
        except Exception as exc:
            run.status = "failed"
            run.message = str(exc)[:1000]
        run.finished_at = datetime.utcnow()
        db.commit()
        results.append({"sourceCode": source_code, "status": run.status, "message": run.message})
    return {"checkedAt": datetime.utcnow().isoformat(), "results": results}


@app.get("/api/updates")
def update_history(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(UpdateRun).order_by(UpdateRun.started_at.desc()).limit(50)).all()
    return [
        {
            "id": item.id,
            "sourceCode": item.source_code,
            "startedAt": item.started_at.isoformat(),
            "finishedAt": item.finished_at.isoformat() if item.finished_at else None,
            "status": item.status,
            "message": item.message,
        }
        for item in items
    ]


@app.get("/api/channels")
def channels(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(BusinessChannel).order_by(BusinessChannel.id)).all()
    return [
        {
            "code": item.code,
            "name": item.name,
            "type": item.channel_type,
            "status": item.lifecycle_status,
            "plannedLaunch": item.planned_launch.isoformat() if item.planned_launch else None,
            "notes": item.notes,
        }
        for item in items
    ]


@app.post("/api/notes", status_code=201)
def create_note(payload: NoteInput, db: Session = Depends(get_db)) -> dict:
    item = AnalysisNote(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_note(item)


@app.get("/api/notes")
def notes(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(AnalysisNote).order_by(AnalysisNote.created_at.desc())).all()
    return [_serialize_note(item) for item in items]


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="dashboard")
