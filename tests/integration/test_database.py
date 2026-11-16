from pathlib import Path

from sqlalchemy import inspect, select
from sqlalchemy.pool import NullPool

from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import Base


async def test_database_creates_the_schema(tmp_path: Path) -> None:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'schema.db').as_posix()}",
        pooling=False,
    )
    try:
        await database.create_schema()
        async with database.engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync: set(inspect(sync).get_table_names())
            )
    finally:
        await database.dispose()

    assert tables == set(Base.metadata.tables)


async def test_database_reuses_the_engine_across_sessions(
    tmp_path: Path,
) -> None:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'sessions.db').as_posix()}",
        pooling=False,
    )
    try:
        await database.create_schema()
        async with database.session() as session:
            assert await session.scalar(select(1)) == 1
        async with database.session() as session:
            assert await session.scalar(select(1)) == 1
    finally:
        await database.dispose()


async def test_presentation_pooling_uses_null_pool(tmp_path: Path) -> None:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'pool.db').as_posix()}",
        pooling=False,
    )
    try:
        assert isinstance(database.engine.pool, NullPool)
        assert database.dialect_name == "sqlite"
    finally:
        await database.dispose()


async def test_pooled_database_keeps_the_default_pool(tmp_path: Path) -> None:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'pooled.db').as_posix()}"
    )
    try:
        assert not isinstance(database.engine.pool, NullPool)
    finally:
        await database.dispose()
