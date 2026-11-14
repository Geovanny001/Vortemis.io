import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vortemis.infrastructure.persistence.models import IngestionState

DEFAULT_PERSIST_INTERVAL = 5.0


@dataclass(frozen=True, slots=True)
class IngestionCheckpoint:
    source_path: str
    device: int
    inode: int
    offset: int


class SqlIngestionState:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load(self, source: Path) -> IngestionCheckpoint | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(IngestionState).where(
                    IngestionState.source_path == str(source)
                )
            )
        if row is None:
            return None
        return IngestionCheckpoint(
            source_path=row.source_path,
            device=row.device,
            inode=row.inode,
            offset=row.offset,
        )

    async def save(self, source: Path, offset: int) -> None:
        stat = await asyncio.to_thread(source.stat)
        values = {
            "source_path": str(source),
            "device": int(stat.st_dev),
            "inode": int(stat.st_ino),
            "offset": int(offset),
            "updated_at": datetime.now(UTC),
        }
        async with self._session_factory() as session:
            await self._upsert(session, values)
            await session.commit()

    async def _upsert(
        self, session: AsyncSession, values: dict[str, Any]
    ) -> None:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgres_insert(IngestionState).values(**values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=["source_path"],
                    set_={
                        "device": statement.excluded.device,
                        "inode": statement.excluded.inode,
                        "offset": statement.excluded.offset,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )
            return
        if dialect == "sqlite":
            statement = sqlite_insert(IngestionState).values(**values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=["source_path"],
                    set_={
                        "device": statement.excluded.device,
                        "inode": statement.excluded.inode,
                        "offset": statement.excluded.offset,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )
            return
        await session.merge(IngestionState(**values))


async def resolve_resume_offset(
    state: SqlIngestionState, source: Path
) -> int:
    if not await asyncio.to_thread(source.exists):
        return 0
    checkpoint = await state.load(source)
    if checkpoint is None:
        return 0
    stat = await asyncio.to_thread(source.stat)
    if checkpoint.device and checkpoint.inode:
        current = (int(stat.st_dev), int(stat.st_ino))
        if (checkpoint.device, checkpoint.inode) != current:
            return 0
    if stat.st_size < checkpoint.offset:
        return 0
    return checkpoint.offset


class CheckpointRecorder:
    def __init__(
        self,
        state: SqlIngestionState,
        source: Path,
        initial_offset: int = 0,
        interval: float = DEFAULT_PERSIST_INTERVAL,
    ) -> None:
        self._state = state
        self._source = source
        self._interval = interval
        self._last_seen = initial_offset
        self._last_saved = initial_offset
        self._last_saved_at = time.monotonic() - interval

    async def __call__(self, offset: int) -> None:
        self._last_seen = offset
        if offset == self._last_saved:
            return
        now = time.monotonic()
        if self._last_saved >= 0 and now - self._last_saved_at < self._interval:
            return
        await self._persist(offset)

    async def flush(self) -> None:
        if self._last_seen != self._last_saved:
            await self._persist(self._last_seen)

    async def _persist(self, offset: int) -> None:
        await self._state.save(self._source, offset)
        self._last_saved = offset
        self._last_saved_at = time.monotonic()
