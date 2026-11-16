import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest

from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.login_throttle import SqlLoginThrottle


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[SqlDatabase]:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'throttle.db').as_posix()}",
        pooling=False,
    )
    await database.create_schema()
    yield database
    await database.dispose()


async def test_locks_after_five_failures(database: SqlDatabase) -> None:
    throttle = SqlLoginThrottle(database)

    for _ in range(5):
        await throttle.register_failure("admin_carles")

    assert await throttle.allow("admin_carles") is False
    assert await throttle.remaining_seconds("admin_carles") > 0


async def test_success_clears_the_failures(database: SqlDatabase) -> None:
    throttle = SqlLoginThrottle(database)
    for _ in range(3):
        await throttle.register_failure("soc_analyst")

    await throttle.register_success("soc_analyst")

    assert await throttle.allow("soc_analyst") is True
    assert await throttle.remaining_seconds("soc_analyst") == 0


async def test_lockout_expires(database: SqlDatabase) -> None:
    throttle = SqlLoginThrottle(
        database, lockout=timedelta(milliseconds=50)
    )
    for _ in range(5):
        await throttle.register_failure("admin_carles")

    assert await throttle.allow("admin_carles") is False
    await asyncio.sleep(0.1)
    assert await throttle.allow("admin_carles") is True


async def test_old_failures_fall_out_of_the_window(
    database: SqlDatabase,
) -> None:
    throttle = SqlLoginThrottle(
        database, window=timedelta(milliseconds=50)
    )
    for _ in range(5):
        await throttle.register_failure("admin_carles")

    await asyncio.sleep(0.1)

    assert await throttle.allow("admin_carles") is True
