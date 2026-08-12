from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import Dataset, Observation, RawArtifact


def upsert_verified_observation(
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
