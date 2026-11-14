from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from vortemis.infrastructure.persistence.ingestion_state import (
    CheckpointRecorder,
    IngestionCheckpoint,
    SqlIngestionState,
    resolve_resume_offset,
)
from vortemis.infrastructure.persistence.models import Base, IngestionState


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class _StubState:
    def __init__(self, checkpoint: IngestionCheckpoint | None) -> None:
        self._checkpoint = checkpoint

    async def load(self, source: Path) -> IngestionCheckpoint | None:
        return self._checkpoint


async def test_state_roundtrip(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("row-1\nrow-2\n", encoding="utf-8")
    state = SqlIngestionState(session_factory)

    await state.save(log_file, 12)
    checkpoint = await state.load(log_file)

    assert checkpoint is not None
    assert checkpoint.offset == 12
    assert checkpoint.source_path == str(log_file)
    assert checkpoint.inode == int(log_file.stat().st_ino)


async def test_state_keeps_one_row_per_source(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("row-1\nrow-2\n", encoding="utf-8")
    state = SqlIngestionState(session_factory)

    await state.save(log_file, 4)
    await state.save(log_file, 8)

    async with session_factory() as session:
        rows = await session.scalar(
            select(func.count()).select_from(IngestionState)
        )
    checkpoint = await state.load(log_file)

    assert rows == 1
    assert checkpoint is not None
    assert checkpoint.offset == 8


async def test_resume_offset_uses_matching_checkpoint(tmp_path: Path) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("row-1\nrow-2\n", encoding="utf-8")
    stat = log_file.stat()
    state = _StubState(
        IngestionCheckpoint(
            source_path=str(log_file),
            device=int(stat.st_dev),
            inode=int(stat.st_ino),
            offset=6,
        )
    )

    assert await resolve_resume_offset(state, log_file) == 6


async def test_resume_offset_restarts_when_file_is_smaller(tmp_path: Path) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("row\n", encoding="utf-8")
    stat = log_file.stat()
    state = _StubState(
        IngestionCheckpoint(
            source_path=str(log_file),
            device=int(stat.st_dev),
            inode=int(stat.st_ino),
            offset=10_000,
        )
    )

    assert await resolve_resume_offset(state, log_file) == 0


async def test_resume_offset_restarts_when_file_identity_changes(
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("row\n", encoding="utf-8")
    state = _StubState(
        IngestionCheckpoint(
            source_path=str(log_file),
            device=1,
            inode=2,
            offset=4,
        )
    )

    assert await resolve_resume_offset(state, log_file) == 0


async def test_resume_offset_without_checkpoint_is_zero(tmp_path: Path) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("row\n", encoding="utf-8")

    assert await resolve_resume_offset(_StubState(None), log_file) == 0
    assert await resolve_resume_offset(_StubState(None), tmp_path / "missing") == 0


async def test_recorder_persists_first_offset_and_flushes_last(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("0123456789", encoding="utf-8")
    state = SqlIngestionState(session_factory)
    recorder = CheckpointRecorder(state, log_file, interval=60.0)

    await recorder(2)
    await recorder(4)

    stored = await state.load(log_file)
    assert stored is not None
    assert stored.offset == 2

    await recorder.flush()

    stored = await state.load(log_file)
    assert stored is not None
    assert stored.offset == 4


async def test_recorder_does_not_reset_a_stored_offset(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    log_file = tmp_path / "conn.log"
    log_file.write_text("0123456789", encoding="utf-8")
    state = SqlIngestionState(session_factory)
    await state.save(log_file, 10)

    recorder = CheckpointRecorder(
        state, log_file, initial_offset=10, interval=60.0
    )
    await recorder.flush()

    stored = await state.load(log_file)
    assert stored is not None
    assert stored.offset == 10
