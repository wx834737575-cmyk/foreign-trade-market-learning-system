from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Dataset, RawArtifact, Source
from ..parsers.sse_freight import PARSER_VERSION, parse_freight_index
from .common import upsert_verified_observation


INDEX_URLS = {
    "SCFI": "https://www.sse.net.cn/index/singleIndex?indexType=scfi",
    "CCFI": "https://www.sse.net.cn/index/singleIndex?indexType=ccfi",
}
DATASET_CODES = {"SCFI": "SCFI_COMPOSITE", "CCFI": "CCFI_COMPOSITE"}


@dataclass(frozen=True)
class ImportResult:
    artifact_sha256: str
    artifact_path: str
    imported: int
    skipped: int
    latest_period: date


def _check_official_url(url: str) -> None:
    if urlparse(url).hostname != "www.sse.net.cn":
        raise ValueError("只允许从上海航运交易所官方域名导入航运指数")


def _fetch(http: httpx.Client, url: str) -> httpx.Response:
    _check_official_url(url)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = http.get(url)
            response.raise_for_status()
            _check_official_url(str(response.url))
            return response
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"上海航运交易所官方页面请求失败: {url}") from last_error


def _artifact(db: Session, source: Source, response: httpx.Response, code: str, period: date) -> RawArtifact:
    content = response.content
    sha256 = hashlib.sha256(content).hexdigest()
    directory = settings.data_dir / "raw" / "SSE" / "latest"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{code}_{period:%Y%m%d}_{sha256[:16]}.html"
    if not path.exists():
        path.write_bytes(content)
    artifact = db.scalar(select(RawArtifact).where(RawArtifact.sha256 == sha256))
    if artifact is None:
        artifact = RawArtifact(
            source_id=source.id,
            source_url=str(response.url),
            content_type=response.headers.get("content-type", "text/html")[:100],
            sha256=sha256,
            local_path=str(path),
            http_status=response.status_code,
            parser_version=PARSER_VERSION,
            quality_status="verified",
        )
        db.add(artifact)
        db.flush()
    else:
        artifact.parser_version = PARSER_VERSION
        artifact.quality_status = "verified"
    return artifact


def import_sse_freight(db: Session, *, client: httpx.Client | None = None) -> ImportResult:
    source = db.scalar(select(Source).where(Source.code == "SSE"))
    if source is None:
        raise RuntimeError("上海航运交易所来源尚未初始化")
    datasets = {
        code: db.scalar(select(Dataset).where(Dataset.code == dataset_code))
        for code, dataset_code in DATASET_CODES.items()
    }
    if any(dataset is None for dataset in datasets.values()):
        raise RuntimeError("SCFI或CCFI综合指数指标尚未初始化")

    owns_client = client is None
    http = client or httpx.Client(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "FTDS/0.2 personal-learning-source-audit"},
    )
    imported = 0
    skipped = 0
    latest_period: date | None = None
    latest_artifact: RawArtifact | None = None
    try:
        for code, url in INDEX_URLS.items():
            response = _fetch(http, url)
            publication = parse_freight_index(response.content, code)
            artifact = _artifact(db, source, response, code, publication.period)
            changed = upsert_verified_observation(
                db,
                dataset=datasets[code],
                artifact=artifact,
                period=publication.period,
                value=publication.value,
                published_at=datetime.combine(publication.period, datetime.min.time()).replace(hour=15),
                methodology_version="SSE latest composite page v1",
                note=(
                    f"官方页面本期值与上期值通过涨跌校验；仅供本地个人学习，不批量镜像历史数据，"
                    f"不用于公开或商业发布；原始证据SHA-256: {artifact.sha256}"
                ),
            )
            imported += int(changed)
            skipped += int(not changed)
            if latest_period is None or publication.period >= latest_period:
                latest_period = publication.period
                latest_artifact = artifact
        source.verification_url = INDEX_URLS["SCFI"]
        source.acquisition_mode = "automatic_learning_only"
        source.notes = "每次仅保存SCFI、CCFI最新综合指数和官方证据，供本地个人学习；不批量抓取历史，不用于公开或商业发布。"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_client:
            http.close()

    if latest_period is None or latest_artifact is None:
        raise RuntimeError("未导入任何航运指数")
    return ImportResult(
        artifact_sha256=latest_artifact.sha256,
        artifact_path=latest_artifact.local_path,
        imported=imported,
        skipped=skipped,
        latest_period=latest_period,
    )
