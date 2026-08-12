from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import RawArtifact, Source


OFFICIAL_QUERY_URL = "https://stats.customs.gov.cn/"
SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv"}
REQUIRED_QUERY_FIELDS = {"start_period", "end_period", "trade_flow", "currency", "product_codes"}


@dataclass(frozen=True)
class RegistrationResult:
    artifact_sha256: str
    artifact_path: str
    metadata_path: str
    already_registered: bool


def _validate_metadata(metadata: dict) -> dict:
    missing = sorted(REQUIRED_QUERY_FIELDS - metadata.keys())
    if missing:
        raise ValueError(f"海关导出查询条件缺少字段: {', '.join(missing)}")
    try:
        start_period = date.fromisoformat(str(metadata["start_period"]))
        end_period = date.fromisoformat(str(metadata["end_period"]))
    except ValueError as exc:
        raise ValueError("海关导出的起止统计期必须为YYYY-MM-DD") from exc
    if start_period > end_period:
        raise ValueError("海关导出的起始统计期不能晚于结束统计期")
    normalized = dict(metadata)
    normalized["start_period"] = start_period.isoformat()
    normalized["end_period"] = end_period.isoformat()
    normalized["source_url"] = OFFICIAL_QUERY_URL
    return normalized


def register_customs_official_export(db: Session, file_path: Path, query_metadata: dict) -> RegistrationResult:
    path = file_path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("海关官方导出文件不存在或为空")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("海关官方导出文件仅接受XLSX、XLS或CSV")
    if urlparse(OFFICIAL_QUERY_URL).hostname != "stats.customs.gov.cn":
        raise ValueError("海关来源入口配置异常")
    metadata = _validate_metadata(query_metadata)
    source = db.scalar(select(Source).where(Source.code == "CUSTOMS"))
    if source is None:
        raise RuntimeError("海关总署来源尚未初始化")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    directory = settings.data_dir / "raw" / "CUSTOMS" / "official_exports"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{metadata['start_period']}_{metadata['end_period']}_{sha256[:16]}{path.suffix.lower()}"
    metadata_path = destination.with_suffix(destination.suffix + ".query.json")
    if not destination.exists():
        shutil.copy2(path, destination)
    sidecar = {
        "source_url": OFFICIAL_QUERY_URL,
        "original_filename": path.name,
        "file_sha256": sha256,
        "query": metadata,
        "parser_status": "pending_first_sample_validation",
    }
    if not metadata_path.exists():
        metadata_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact = db.scalar(select(RawArtifact).where(RawArtifact.sha256 == sha256))
    already_registered = artifact is not None
    if artifact is None:
        artifact = RawArtifact(
            source_id=source.id,
            source_url=OFFICIAL_QUERY_URL,
            content_type=mimetypes.guess_type(destination.name)[0] or "application/octet-stream",
            sha256=sha256,
            local_path=str(destination),
            http_status=None,
            parser_version=None,
            quality_status="pending_parser",
        )
        db.add(artifact)
    db.commit()
    return RegistrationResult(sha256, str(destination), str(metadata_path), already_registered)
