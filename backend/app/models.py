from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    authority_level: Mapped[str] = mapped_column(String(32), default="official")
    homepage_url: Mapped[str] = mapped_column(Text)
    verification_url: Mapped[str | None] = mapped_column(Text)
    acquisition_mode: Mapped[str] = mapped_column(String(32), default="manual_review")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="source")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    frequency: Mapped[str] = mapped_column(String(24))
    unit: Mapped[str] = mapped_column(String(40))
    methodology: Mapped[str | None] = mapped_column(Text)
    expected_release_rule: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship(back_populates="datasets")
    observations: Mapped[list[Observation]] = relationship(back_populates="dataset")


class RawArtifact(Base):
    __tablename__ = "raw_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_url: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    local_path: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int | None]
    parser_version: Mapped[str | None] = mapped_column(String(40))
    quality_status: Mapped[str] = mapped_column(String(32), default="pending")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("dataset_id", "period", "vintage", name="uq_observation_vintage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey("raw_artifacts.id"), index=True)
    period: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    unit: Mapped[str] = mapped_column(String(40))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    vintage: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_status: Mapped[str] = mapped_column(String(32), default="unverified")
    methodology_version: Mapped[str | None] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship(back_populates="observations")


class AnalysisNote(Base):
    __tablename__ = "analysis_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(24), default="medium")
    evidence_snapshot: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BusinessChannel(Base):
    __tablename__ = "business_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    channel_type: Mapped[str] = mapped_column(String(40))
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="planned")
    planned_launch: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class BusinessSnapshot(Base):
    __tablename__ = "business_snapshots"
    __table_args__ = (
        UniqueConstraint("channel_id", "period", name="uq_business_snapshot_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("business_channels.id"), index=True)
    period: Mapped[date] = mapped_column(Date, index=True)
    visits: Mapped[int | None]
    inquiries: Mapped[int | None]
    qualified_leads: Mapped[int | None]
    quotes: Mapped[int | None]
    orders: Mapped[int | None]
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    ad_spend: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    source_file_sha256: Mapped[str | None] = mapped_column(String(64))
    quality_status: Mapped[str] = mapped_column(String(32), default="user_reported")


class ReleaseCalendar(Base):
    __tablename__ = "release_calendar"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    statistical_period: Mapped[date] = mapped_column(Date)
    expected_from: Mapped[date | None] = mapped_column(Date)
    expected_to: Mapped[date | None] = mapped_column(Date)
    actual_release_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="waiting")
    source_url: Mapped[str | None] = mapped_column(Text)


class UpdateRun(Base):
    __tablename__ = "update_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="running")
    message: Mapped[str | None] = mapped_column(Text)
