from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Dataset, Observation, RawArtifact, Source
from ..parsers.nbs_pmi import PARSER_VERSION, parse_nbs_pmi


NBS_PMI_JUNE_2026_URL = "https://www.stats.gov.cn/sj/zxfbhjd/202606/t20260630_1964032.html"


@dataclass(frozen=True)
class ImportResult:
    artifact_sha256: str
    artifact_path: str
    imported: int
    skipped: int
    latest_period: date
    latest_value: Decimal


def _save_raw(content: bytes, sha256: str) -> Path:
    directory = settings.data_dir / "raw" / "NBS" / "pmi"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"2026-06_{sha256[:16]}.html"
    if not path.exists():
        path.write_bytes(content)
    return path


def import_nbs_pmi(
    db: Session,
    *,
    url: str = NBS_PMI_JUNE_2026_URL,
    expected_period: date = date(2026, 6, 1),
    expected_value: Decimal = Decimal("50.3"),
    client: httpx.Client | None = None,
) -> ImportResult:
    if urlparse(url).hostname != "www.stats.gov.cn":
        raise ValueError("只允许从国家统计局官方域名导入PMI")

    owns_client = client is None
    http = client or httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "FTDS/0.1 official-source-audit"})
    try:
        response = http.get(url)
        response.raise_for_status()
    finally:
        if owns_client:
            http.close()

    if urlparse(str(response.url)).hostname != "www.stats.gov.cn":
        raise ValueError("国家统计局页面发生非官方域名跳转")

    content = response.content
    sha256 = hashlib.sha256(content).hexdigest()
    raw_path = _save_raw(content, sha256)
    source = db.scalar(select(Source).where(Source.code == "NBS"))
    dataset = db.scalar(select(Dataset).where(Dataset.code == "CN_MANUFACTURING_PMI"))
    if source is None or dataset is None:
        raise RuntimeError("国家统计局来源或制造业PMI指标尚未初始化")

    artifact = db.scalar(select(RawArtifact).where(RawArtifact.sha256 == sha256))
    if artifact is None:
        artifact = RawArtifact(
            source_id=source.id,
            source_url=url,
            content_type=response.headers.get("content-type", "text/html"),
            sha256=sha256,
            local_path=str(raw_path),
            http_status=response.status_code,
            parser_version=PARSER_VERSION,
            quality_status="pending",
        )
        db.add(artifact)
        db.flush()

    try:
        publication = parse_nbs_pmi(content)
        latest = max(publication.records, key=lambda item: item.period)
        if latest.period != expected_period or latest.value != expected_value:
            raise ValueError(
                f"官方页面最新值未通过双重校验: {latest.period}={latest.value}, "
                f"预期 {expected_period}={expected_value}"
            )
    except Exception:
        artifact.quality_status = "rejected"
        db.commit()
        raise

    source.verification_url = url
    artifact.parser_version = PARSER_VERSION
    artifact.quality_status = "verified"
    imported = 0
    skipped = 0
    for record in publication.records:
        verified_exists = db.scalar(
            select(Observation.id).where(
                Observation.dataset_id == dataset.id,
                Observation.period == record.period,
                Observation.quality_status == "verified",
            )
        )
        if verified_exists is not None:
            skipped += 1
            continue
        db.execute(
            update(Observation)
            .where(Observation.dataset_id == dataset.id, Observation.period == record.period)
            .values(is_current=False)
        )
        latest_vintage = db.scalar(
            select(func.max(Observation.vintage)).where(
                Observation.dataset_id == dataset.id,
                Observation.period == record.period,
            )
        ) or 0
        db.add(
            Observation(
                dataset_id=dataset.id,
                artifact_id=artifact.id,
                period=record.period,
                value=record.value,
                unit="%",
                published_at=publication.published_at,
                vintage=latest_vintage + 1,
                is_current=True,
                quality_status="verified",
                methodology_version="NBS PMI seasonal-adjusted",
                note=f"官方页面解析；原始证据SHA-256: {sha256}",
            )
        )
        imported += 1
    db.commit()
    return ImportResult(sha256, str(raw_path), imported, skipped, latest.period, latest.value)


def main() -> None:
    with SessionLocal() as db:
        result = import_nbs_pmi(db)
    print(
        f"NBS PMI import complete: period={result.latest_period}, value={result.latest_value}, "
        f"imported={result.imported}, skipped={result.skipped}, sha256={result.artifact_sha256}"
    )


if __name__ == "__main__":
    main()
