from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.jobs.models import CreateJobRequest, JobSource, JobView, utc_now


class JobStore:
    async def initialize(self) -> None: ...
    async def create(self, job: JobView) -> tuple[JobView, bool]: ...
    async def get(self, job_id: str) -> JobView | None: ...
    async def get_by_identity(self, device_id: str, request_id: str) -> JobView | None: ...
    async def list(self, device_id: str, limit: int = 50) -> list[JobView]: ...
    async def update(self, job_id: str, **changes: Any) -> JobView: ...
    async def redact_source(self, job_id: str) -> JobView: ...


class MemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._items: dict[str, JobView] = {}
        self._identities: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        return None

    async def create(self, job: JobView) -> tuple[JobView, bool]:
        async with self._lock:
            identity = (job.device_id, job.client_request_id)
            existing_id = self._identities.get(identity)
            if existing_id:
                return self._items[existing_id].model_copy(deep=True), True
            self._items[job.job_id] = job.model_copy(deep=True)
            self._identities[identity] = job.job_id
            return job.model_copy(deep=True), False

    async def get(self, job_id: str) -> JobView | None:
        async with self._lock:
            item = self._items.get(job_id)
            return item.model_copy(deep=True) if item else None

    async def get_by_identity(self, device_id: str, request_id: str) -> JobView | None:
        async with self._lock:
            job_id = self._identities.get((device_id, request_id))
            item = self._items.get(job_id) if job_id else None
            return item.model_copy(deep=True) if item else None

    async def list(self, device_id: str, limit: int = 50) -> list[JobView]:
        async with self._lock:
            items = [item for item in self._items.values() if item.device_id == device_id]
            items.sort(key=lambda item: item.created_at, reverse=True)
            return [item.model_copy(deep=True) for item in items[:limit]]

    async def update(self, job_id: str, **changes: Any) -> JobView:
        async with self._lock:
            current = self._items[job_id]
            changes.setdefault("updated_at", utc_now())
            updated = current.model_copy(update=changes, deep=True)
            self._items[job_id] = updated
            return updated.model_copy(deep=True)

    async def redact_source(self, job_id: str) -> JobView:
        return await self.update(
            job_id,
            source=JobSource(type="shared_url", value="已按用户请求删除"),
        )


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "verification_jobs"
    __table_args__ = (UniqueConstraint("device_id", "client_request_id"),)

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    client_request_id: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(30))
    source_value: Mapped[str] = mapped_column(Text)
    platform_hint: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mode: Mapped[str] = mapped_column(String(10))
    verification_mode: Mapped[str] = mapped_column(String(10), default="speed")
    status: Mapped[str] = mapped_column(String(20), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    display_text: Mapped[str] = mapped_column(String(240))
    progress_hint: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


def _to_view(row: JobRow) -> JobView:
    return JobView(
        job_id=row.job_id,
        device_id=row.device_id,
        client_request_id=row.client_request_id,
        source=JobSource(type=row.source_type, value=row.source_value, platform_hint=row.platform_hint),
        mode=row.mode,
        verification_mode=row.verification_mode,
        status=row.status,
        stage=row.stage,
        display_text=row.display_text,
        progress_hint=row.progress_hint,
        sequence=row.sequence,
        elapsed_ms=row.elapsed_ms,
        cancel_requested=row.cancel_requested,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        result=row.result,
        error_code=row.error_code,
        error_message=row.error_message,
    )


class SqlJobStore(JobStore):
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            columns = await connection.run_sync(
                lambda sync_connection: {
                    item["name"]
                    for item in inspect(sync_connection).get_columns(
                        JobRow.__tablename__
                    )
                }
            )
            if "verification_mode" not in columns:
                await connection.execute(text(
                    "ALTER TABLE verification_jobs "
                    "ADD COLUMN verification_mode VARCHAR(10) "
                    "NOT NULL DEFAULT 'speed'"
                ))

    async def create(self, job: JobView) -> tuple[JobView, bool]:
        async with self.sessions() as session:
            existing = await self._find_identity(session, job.device_id, job.client_request_id)
            if existing:
                return _to_view(existing), True
            row = JobRow(
                job_id=job.job_id, device_id=job.device_id,
                client_request_id=job.client_request_id,
                source_type=job.source.type, source_value=job.source.value,
                platform_hint=job.source.platform_hint, mode=job.mode,
                verification_mode=job.verification_mode,
                status=job.status, stage=job.stage, display_text=job.display_text,
                progress_hint=job.progress_hint, sequence=job.sequence,
                elapsed_ms=job.elapsed_ms, cancel_requested=False,
                created_at=job.created_at, updated_at=job.updated_at,
            )
            session.add(row)
            await session.commit()
            return _to_view(row), False

    async def _find_identity(self, session: AsyncSession, device_id: str, request_id: str) -> JobRow | None:
        result = await session.execute(select(JobRow).where(
            JobRow.device_id == device_id,
            JobRow.client_request_id == request_id,
        ))
        return result.scalar_one_or_none()

    async def get(self, job_id: str) -> JobView | None:
        async with self.sessions() as session:
            row = await session.get(JobRow, job_id)
            return _to_view(row) if row else None

    async def get_by_identity(self, device_id: str, request_id: str) -> JobView | None:
        async with self.sessions() as session:
            row = await self._find_identity(session, device_id, request_id)
            return _to_view(row) if row else None

    async def list(self, device_id: str, limit: int = 50) -> list[JobView]:
        async with self.sessions() as session:
            result = await session.execute(
                select(JobRow).where(JobRow.device_id == device_id)
                .order_by(JobRow.created_at.desc()).limit(limit)
            )
            return [_to_view(row) for row in result.scalars()]

    async def update(self, job_id: str, **changes: Any) -> JobView:
        async with self.sessions() as session:
            row = await session.get(JobRow, job_id, with_for_update=True)
            if not row:
                raise KeyError(job_id)
            changes.setdefault("updated_at", utc_now())
            for key, value in changes.items():
                setattr(row, key, value)
            await session.commit()
            return _to_view(row)

    async def redact_source(self, job_id: str) -> JobView:
        async with self.sessions() as session:
            row = await session.get(JobRow, job_id, with_for_update=True)
            if not row:
                raise KeyError(job_id)
            row.source_value = "已按用户请求删除"
            row.platform_hint = None
            row.updated_at = utc_now()
            await session.commit()
            return _to_view(row)
