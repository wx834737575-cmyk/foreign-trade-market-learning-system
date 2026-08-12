from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Dataset, RawArtifact, Source
from ..parsers.cfets_usdcny import PARSER_VERSION, parse_usdcny_history, parse_usdcny_latest
from .common import upsert_verified_observation


PAGE_URL = "https://www.chinamoney.com.cn/chinese/bkccpr/index.html?tab=2"
HISTORY_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew"
LATEST_URL = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"


@dataclass(frozen=True)
class ImportResult:
    artifact_sha256: str
    artifact_path: str
    imported: int
    skipped: int
    latest_period: date
    latest_value: float


def _check_official_url(url: str) -> None:
    if urlparse(url).hostname != "www.chinamoney.com.cn":
        raise ValueError("只允许从中国货币网官方域名导入USD/CNY中间价")


def _request(http: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    _check_official_url(url)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = http.request(method, url, **kwargs)
            response.raise_for_status()
            _check_official_url(str(response.url))
            return response
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"中国货币网官方数据请求失败: {url}") from last_error


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
    directory = settings.data_dir / "raw" / "CFETS" / "usdcny"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}_{sha256[:16]}.json"
    if not path.exists():
        path.write_bytes(content)
    artifact = db.scalar(select(RawArtifact).where(RawArtifact.sha256 == sha256))
    if artifact is None:
        artifact = RawArtifact(
            source_id=source.id,
            source_url=str(response.url),
            content_type=response.headers.get("content-type", "application/json")[:100],
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


def import_cfets_usdcny(
    db: Session,
    *,
    today: date = date(2026, 7, 20),
    history_days: int = 364,
    client: httpx.Client | None = None,
) -> ImportResult:
    source = db.scalar(select(Source).where(Source.code == "CFETS"))
    dataset = db.scalar(select(Dataset).where(Dataset.code == "CN_USDCNY_CENTRAL_PARITY"))
    if source is None or dataset is None:
        raise RuntimeError("中国货币网来源或USD/CNY中间价指标尚未初始化")

    if not 1 <= history_days <= 364:
        raise ValueError("中国货币网单次历史查询区间必须为1至364天")
    start_date = today - timedelta(days=history_days)
    owns_client = client is None
    http = client or httpx.Client(
        timeout=45,
        follow_redirects=True,
        headers={
            "User-Agent": "FTDS/0.2 official-source-audit",
            "Referer": PAGE_URL,
        },
    )
    try:
        pages = []
        page_num = 1
        while True:
            history_query_url = (
                f"{HISTORY_URL}?startDate={start_date.isoformat()}&endDate={today.isoformat()}"
                f"&currency=USD/CNY&pageNum={page_num}&pageSize=50"
            )
            history_response = _request(http, "POST", history_query_url)
            records = json.loads(history_response.content).get("records")
            if records == [] and page_num > 1:
                break
            history = parse_usdcny_history(history_response.content)
            pages.append((history_response, history))
            if len(history.points) < 50:
                break
            page_num += 1
            if page_num > 20:
                raise ValueError("中国货币网历史查询分页数量异常")
        latest_response = _request(http, "GET", LATEST_URL)
        latest = parse_usdcny_latest(latest_response.content)
        all_points = [point for _, page in pages for point in page.points]
        by_period = {point.period: point for point in all_points}
        if len(by_period) != len(all_points):
            raise ValueError("中国货币网历史接口分页出现重复日期")
        ordered_points = sorted(by_period.values(), key=lambda point: point.period)
        if not ordered_points or ordered_points[-1].period != latest.period or ordered_points[-1].value != latest.value:
            raise ValueError("中国货币网历史接口与最新中间价文件未通过交叉核验")

        page_artifacts = []
        for number, (response, history) in enumerate(pages, start=1):
            page_artifacts.append(
                _artifact(
                    db,
                    source=source,
                    response=response,
                    label=f"history_{history.end_date:%Y%m%d}_p{number}",
                    quality_status="verified",
                )
            )
        _artifact(
            db,
            source=source,
            response=latest_response,
            label=f"latest_{latest.period:%Y%m%d}",
            quality_status="verified_supporting",
        )
        imported = 0
        skipped = 0
        for (response, history), artifact in zip(pages, page_artifacts, strict=True):
            for point in history.points:
                published_at = latest.published_at if point.period == latest.period else datetime.combine(point.period, datetime.min.time()).replace(hour=9, minute=15)
                changed = upsert_verified_observation(
                    db,
                    dataset=dataset,
                    artifact=artifact,
                    period=point.period,
                    value=point.value,
                    published_at=published_at,
                    methodology_version="CFETS USD/CNY central parity JSON v1",
                    note=(
                        "中国货币网历史接口与当日中间价文件交叉核验；"
                        f"原始证据SHA-256: {artifact.sha256}"
                    ),
                )
                imported += int(changed)
                skipped += int(not changed)
        source.verification_url = PAGE_URL
        source.acquisition_mode = "automatic_with_review"
        source.notes = "中国外汇交易中心受权发布；历史接口与当日官方JSON交叉核验，保存原始文件和SHA-256。"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_client:
            http.close()

    return ImportResult(
        artifact_sha256=page_artifacts[0].sha256,
        artifact_path=page_artifacts[0].local_path,
        imported=imported,
        skipped=skipped,
        latest_period=latest.period,
        latest_value=float(latest.value),
    )
