from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Dataset, RawArtifact, Source
from ..parsers.nbs_core_monthly import PARSER_VERSION, PARSERS, parse_release_index
from .common import upsert_verified_observation


RELEASE_INDEX_URL = "https://www.stats.gov.cn/sj/zxfb/"
DATASET_CODES = {
    "CN_CPI_YOY",
    "CN_CPI_MOM",
    "CN_PPI_YOY",
    "CN_PPI_MOM",
    "CN_INDUSTRIAL_VALUE_ADDED_YOY",
    "CN_RETAIL_SALES_VALUE",
    "CN_RETAIL_SALES_YOY",
}


@dataclass(frozen=True)
class ImportResult:
    artifact_sha256: str
    artifact_path: str
    imported: int
    skipped: int
    latest_period: date


def _check_official_url(url: str) -> None:
    if urlparse(url).hostname != "www.stats.gov.cn":
        raise ValueError("只允许从国家统计局官方域名导入核心月度数据")


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
    raise RuntimeError(f"国家统计局官方发布页请求失败: {url}") from last_error


def _artifact(
    db: Session,
    *,
    source: Source,
    response: httpx.Response,
    label: str,
    quality_status: str,
) -> RawArtifact:
    content = response.content
    sha256 = hashlib.sha256(content).hexdigest()
    directory = settings.data_dir / "raw" / "NBS" / "core_monthly"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}_{sha256[:16]}.html"
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
            quality_status=quality_status,
        )
        db.add(artifact)
        db.flush()
    else:
        artifact.parser_version = PARSER_VERSION
        artifact.quality_status = quality_status
    return artifact


def import_nbs_core_monthly(
    db: Session,
    *,
    index_url: str = RELEASE_INDEX_URL,
    client: httpx.Client | None = None,
) -> ImportResult:
    source = db.scalar(select(Source).where(Source.code == "NBS"))
    dataset_rows = db.scalars(select(Dataset).where(Dataset.code.in_(DATASET_CODES))).all()
    datasets = {dataset.code: dataset for dataset in dataset_rows}
    if source is None or len(datasets) != len(DATASET_CODES):
        raise RuntimeError("国家统计局来源或核心月度指标尚未完整初始化")

    owns_client = client is None
    http = client or httpx.Client(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "FTDS/0.3 official-source-audit"},
    )
    try:
        index_response = _fetch(http, index_url)
        release_index = parse_release_index(index_response.content, index_url)
        parsed = []
        for kind, parser in PARSERS.items():
            response = _fetch(http, release_index.urls[kind])
            publication = parser(response.content)
            parsed.append((response, publication))

        index_artifact = _artifact(
            db,
            source=source,
            response=index_response,
            label="release_index",
            quality_status="verified_supporting",
        )
        imported = 0
        skipped = 0
        latest_period: date | None = None
        for response, publication in parsed:
            artifact = _artifact(
                db,
                source=source,
                response=response,
                label=f"{publication.kind}_{publication.period:%Y%m}",
                quality_status="verified",
            )
            for item in publication.values:
                changed = upsert_verified_observation(
                    db,
                    dataset=datasets[item.dataset_code],
                    artifact=artifact,
                    period=publication.period,
                    value=item.value,
                    published_at=publication.published_at,
                    methodology_version="NBS official release page v1",
                    note=(
                        "国家统计局数据发布目录自动发现；标题、正文及可用表格字段交叉校验；"
                        f"目录证据SHA-256: {index_artifact.sha256}；发布页证据SHA-256: {artifact.sha256}"
                    ),
                )
                imported += int(changed)
                skipped += int(not changed)
            if latest_period is None or publication.period > latest_period:
                latest_period = publication.period
        source.verification_url = RELEASE_INDEX_URL
        source.acquisition_mode = "automatic_with_review"
        source.notes = (
            "核心月度指标从国家统计局数据发布目录自动发现，保存发布页原文和SHA-256；"
            "国家数据动态查询页仅作为人工核验入口，不依赖其非公开接口。"
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_client:
            http.close()

    if latest_period is None:
        raise RuntimeError("国家统计局核心月度数据未导入任何观测值")
    return ImportResult(
        artifact_sha256=index_artifact.sha256,
        artifact_path=index_artifact.local_path,
        imported=imported,
        skipped=skipped,
        latest_period=latest_period,
    )
