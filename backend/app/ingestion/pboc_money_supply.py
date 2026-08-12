from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Dataset, Observation, RawArtifact, Source
from ..parsers.pboc_money_supply_table import (
    PARSER_VERSION,
    MoneySupplyPoint,
    parse_money_overview_url,
    parse_money_supply_html,
    parse_money_supply_links,
    parse_money_supply_workbook,
    parse_year_links,
)


PBOC_STATISTICS_INDEX_URL = "https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"


@dataclass(frozen=True)
class ImportResult:
    artifact_sha256: str
    artifact_path: str
    imported: int
    skipped: int
    latest_period: date


def _check_official_url(url: str) -> None:
    if urlparse(url).hostname != "www.pbc.gov.cn":
        raise ValueError("只允许从中国人民银行官方域名导入货币供应量数据")


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
    raise RuntimeError(f"人民银行官方文件下载失败: {url}") from last_error


def _save_raw(content: bytes, *, year: int, url: str, sha256: str) -> Path:
    directory = settings.data_dir / "raw" / "PBOC" / "money_supply"
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(url).path).suffix.lower() or ".bin"
    path = directory / f"{year}_{sha256[:16]}{suffix}"
    if not path.exists():
        path.write_bytes(content)
    return path


def _published_at(url: str) -> datetime | None:
    match = re.search(r"/(20\d{12})\d*\.(?:xlsx?|htm|html|pdf)$", urlparse(url).path, re.I)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _artifact(
    db: Session,
    *,
    source: Source,
    url: str,
    response: httpx.Response,
    year: int,
    quality_status: str,
) -> RawArtifact:
    content = response.content
    sha256 = hashlib.sha256(content).hexdigest()
    raw_path = _save_raw(content, year=year, url=url, sha256=sha256)
    artifact = db.scalar(select(RawArtifact).where(RawArtifact.sha256 == sha256))
    if artifact is None:
        artifact = RawArtifact(
            source_id=source.id,
            source_url=url,
            content_type=response.headers.get("content-type", "application/octet-stream")[:100],
            sha256=sha256,
            local_path=str(raw_path),
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


def _upsert_observation(
    db: Session,
    *,
    dataset: Dataset,
    artifact: RawArtifact,
    period: date,
    value: Decimal,
    published_at: datetime | None,
    methodology_version: str,
    note: str,
) -> bool:
    current = db.scalar(
        select(Observation).where(
            Observation.dataset_id == dataset.id,
            Observation.period == period,
            Observation.is_current.is_(True),
        )
    )
    if (
        current is not None
        and current.artifact_id == artifact.id
        and Decimal(current.value) == value
        and current.methodology_version == methodology_version
        and current.quality_status == "verified"
    ):
        return False
    db.execute(
        update(Observation)
        .where(Observation.dataset_id == dataset.id, Observation.period == period)
        .values(is_current=False)
    )
    latest_vintage = db.scalar(
        select(func.max(Observation.vintage)).where(
            Observation.dataset_id == dataset.id,
            Observation.period == period,
        )
    ) or 0
    db.add(
        Observation(
            dataset_id=dataset.id,
            artifact_id=artifact.id,
            period=period,
            value=value,
            unit=dataset.unit,
            published_at=published_at,
            vintage=latest_vintage + 1,
            is_current=True,
            quality_status="verified",
            methodology_version=methodology_version,
            note=note,
        )
    )
    db.flush()
    return True


def _derive_yoy(
    db: Session,
    *,
    datasets: dict[str, Dataset],
    artifacts_by_period: dict[date, RawArtifact],
) -> tuple[int, int]:
    imported = 0
    skipped = 0
    pairs = (
        ("CN_M2_BALANCE", "CN_M2_YOY"),
        ("CN_M1_BALANCE", "CN_M1_YOY"),
    )
    for balance_code, yoy_code in pairs:
        balance_dataset = datasets[balance_code]
        yoy_dataset = datasets[yoy_code]
        rows = db.scalars(
            select(Observation)
            .where(
                Observation.dataset_id == balance_dataset.id,
                Observation.is_current.is_(True),
                Observation.quality_status == "verified",
            )
            .order_by(Observation.period)
        ).all()
        by_period = {row.period: row for row in rows}
        for period, current in by_period.items():
            previous_period = date(period.year - 1, period.month, 1)
            previous = by_period.get(previous_period)
            if previous is None or Decimal(previous.value) == 0:
                continue
            value = (
                (Decimal(current.value) - Decimal(previous.value))
                / Decimal(previous.value)
                * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            artifact = artifacts_by_period.get(period)
            if artifact is None and current.artifact_id is not None:
                artifact = db.get(RawArtifact, current.artifact_id)
            if artifact is None:
                continue
            changed = _upsert_observation(
                db,
                dataset=yoy_dataset,
                artifact=artifact,
                period=period,
                value=value,
                published_at=current.published_at,
                methodology_version="Derived from PBOC official balances; comparable current vintages",
                note=(
                    f"由人民银行官方余额精确计算：({current.value}-{previous.value})/"
                    f"{previous.value}×100；比较期 {previous_period:%Y-%m}；证据SHA-256: {artifact.sha256}"
                ),
            )
            imported += int(changed)
            skipped += int(not changed)
    return imported, skipped


def _years_to_import(db: Session, available: dict[int, str], today: date) -> list[int]:
    current_year = today.year
    required = [year for year in range(current_year - 2, current_year + 1) if year in available]
    m2 = db.scalar(select(Dataset).where(Dataset.code == "CN_M2_BALANCE"))
    if m2 is None:
        return required
    previous_count = db.scalar(
        select(func.count(Observation.id)).where(
            Observation.dataset_id == m2.id,
            Observation.period >= date(current_year - 2, 1, 1),
            Observation.period < date(current_year, 1, 1),
            Observation.is_current.is_(True),
            Observation.quality_status == "verified",
        )
    ) or 0
    return [current_year] if previous_count >= 24 and current_year in available else required


def import_pboc_money_supply(
    db: Session,
    *,
    index_url: str = PBOC_STATISTICS_INDEX_URL,
    years: tuple[int, ...] | None = None,
    today: date = date(2026, 7, 20),
    client: httpx.Client | None = None,
) -> ImportResult:
    _check_official_url(index_url)
    source = db.scalar(select(Source).where(Source.code == "PBOC"))
    if source is None:
        raise RuntimeError("人民银行来源尚未初始化")
    dataset_rows = db.scalars(
        select(Dataset).where(
            Dataset.code.in_([
                "CN_M0_BALANCE",
                "CN_M1_BALANCE",
                "CN_M2_BALANCE",
                "CN_M1_YOY",
                "CN_M2_YOY",
            ])
        )
    ).all()
    datasets = {item.code: item for item in dataset_rows}
    if len(datasets) != 5:
        raise RuntimeError("人民银行货币供应量指标尚未完整初始化")

    owns_client = client is None
    http = client or httpx.Client(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": "FTDS/0.2 official-source-audit"},
    )
    imported = 0
    skipped = 0
    latest_period: date | None = None
    latest_artifact: RawArtifact | None = None
    artifacts_by_period: dict[date, RawArtifact] = {}
    try:
        index_response = _fetch(http, index_url)
        available = parse_year_links(index_response.content, index_url)
        selected_years = sorted(set(years or _years_to_import(db, available, today)))
        missing_years = [year for year in selected_years if year not in available]
        if missing_years:
            raise ValueError(f"人民银行统计总页缺少年度入口: {missing_years}")

        for year in selected_years:
            year_response = _fetch(http, available[year])
            overview_url = parse_money_overview_url(year_response.content, available[year])
            overview_response = _fetch(http, overview_url)
            links = parse_money_supply_links(overview_response.content, overview_url)
            html_response = _fetch(http, links.html_url)
            workbook_response = _fetch(http, links.workbook_url)
            workbook_artifact = _artifact(
                db,
                source=source,
                url=links.workbook_url,
                response=workbook_response,
                year=year,
                quality_status="pending",
            )
            html_artifact = _artifact(
                db,
                source=source,
                url=links.html_url,
                response=html_response,
                year=year,
                quality_status="pending_supporting",
            )
            try:
                points = parse_money_supply_workbook(workbook_response.content, year)
                html_values = parse_money_supply_html(html_response.content, year)
                main_points = [point for point in points if point.period.year == year]
                workbook_values = {(point.dataset_code, point.period): point.value for point in main_points}
                if workbook_values != html_values:
                    raise ValueError(f"{year}年货币供应量XLSX与HTML未通过逐项交叉核验")
            except Exception:
                workbook_artifact.quality_status = "rejected"
                html_artifact.quality_status = "rejected"
                db.commit()
                raise

            workbook_artifact.quality_status = "verified"
            html_artifact.quality_status = "verified_supporting"
            publication_time = _published_at(links.workbook_url) or _published_at(links.html_url)
            for point in points:
                dataset = datasets[point.dataset_code]
                changed = _upsert_observation(
                    db,
                    dataset=dataset,
                    artifact=workbook_artifact,
                    period=point.period,
                    value=point.value,
                    published_at=publication_time,
                    methodology_version=point.methodology_version,
                    note=(
                        f"人民银行年度统计页自动发现；XLSX与HTML逐项一致；"
                        f"{point.note + '；' if point.note else ''}原始证据SHA-256: {workbook_artifact.sha256}"
                    ),
                )
                imported += int(changed)
                skipped += int(not changed)
                artifacts_by_period[point.period] = workbook_artifact
                if latest_period is None or point.period > latest_period:
                    latest_period = point.period
                    latest_artifact = workbook_artifact
            db.commit()
    finally:
        if owns_client:
            http.close()

    derived_imported, derived_skipped = _derive_yoy(
        db,
        datasets=datasets,
        artifacts_by_period=artifacts_by_period,
    )
    imported += derived_imported
    skipped += derived_skipped
    source.verification_url = index_url
    source.acquisition_mode = "automatic_with_review"
    source.notes = (
        "以统计数据年度入口自动发现货币供应量；XLSX为主数据，HTML逐项交叉核验；"
        "原始文件、哈希、观测值版本和M1口径修订均长期保留。"
    )
    datasets["CN_M1_BALANCE"].methodology = (
        "2025年起采用人民银行修订口径；2024年使用2025年表内发布的可比回溯值作为当前版本，旧口径保留为历史版本。"
    )
    datasets["CN_M1_YOY"].methodology = "由人民银行新口径可比余额按同月同比精确计算。"
    datasets["CN_M2_YOY"].methodology = "由人民银行官方M2余额按同月同比精确计算。"
    db.commit()

    if latest_artifact is None or latest_period is None:
        raise RuntimeError("人民银行货币供应量没有导入任何可用月份")
    return ImportResult(
        artifact_sha256=latest_artifact.sha256,
        artifact_path=latest_artifact.local_path,
        imported=imported,
        skipped=skipped,
        latest_period=latest_period,
    )


def main() -> None:
    with SessionLocal() as db:
        result = import_pboc_money_supply(db)
    print(
        f"PBOC money supply import complete: latest={result.latest_period}, "
        f"imported={result.imported}, skipped={result.skipped}, sha256={result.artifact_sha256}"
    )


if __name__ == "__main__":
    main()
