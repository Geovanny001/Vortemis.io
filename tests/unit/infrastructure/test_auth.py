import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from vortemis.infrastructure.persistence.auth import (
    authenticate_operator,
    hash_password,
    seed_default_operators,
    verify_password,
)
from vortemis.infrastructure.persistence.models import Base, SocOperator


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_hash_password_roundtrip() -> None:
    stored = hash_password("VortemisAdmin2026!")
    assert stored != "VortemisAdmin2026!"
    assert verify_password("VortemisAdmin2026!", stored) is True


def test_verify_password_rejects_wrong_password() -> None:
    stored = hash_password("correct-horse")
    assert verify_password("wrong-horse", stored) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("anything", "not-a-valid-hash") is False


async def test_seed_default_operators_creates_roles(session_factory) -> None:
    async with session_factory() as session:
        await seed_default_operators(session)
        await session.commit()
        rows = (
            await session.execute(select(SocOperator.username, SocOperator.role))
        ).all()
    roles = dict(rows)
    assert roles == {
        "admin_carles": "admin",
        "soc_analyst": "analyst",
    }


async def test_seed_default_operators_is_idempotent(session_factory) -> None:
    async with session_factory() as session:
        await seed_default_operators(session)
        await seed_default_operators(session)
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(SocOperator))
    assert count == 2


async def test_seed_default_operators_uses_environment(
    session_factory, monkeypatch
) -> None:
    monkeypatch.setenv("VORTEMIS_ADMIN_USERNAME", "custom_admin")
    monkeypatch.setenv("VORTEMIS_ADMIN_PASSWORD", "CustomAdminPassword!")
    monkeypatch.setenv("VORTEMIS_ANALYST_USERNAME", "custom_analyst")
    monkeypatch.setenv("VORTEMIS_ANALYST_PASSWORD", "CustomAnalystPassword!")

    async with session_factory() as session:
        await seed_default_operators(session)
        await session.commit()
        rows = (
            await session.execute(select(SocOperator.username, SocOperator.role))
        ).all()
        operator = await authenticate_operator(
            session, "custom_admin", "CustomAdminPassword!"
        )

    assert dict(rows) == {
        "custom_admin": "admin",
        "custom_analyst": "analyst",
    }
    assert operator is not None
    assert operator.role == "admin"


async def test_authenticate_operator_success(session_factory) -> None:
    async with session_factory() as session:
        await seed_default_operators(session)
        await session.commit()
        operator = await authenticate_operator(session, "admin_carles", "VortemisAdmin2026!")
    assert operator is not None
    assert operator.role == "admin"


async def test_authenticate_operator_rejects_invalid_credentials(session_factory) -> None:
    async with session_factory() as session:
        await seed_default_operators(session)
        await session.commit()
        bad_password = await authenticate_operator(
            session, "admin_carles", "wrong-password"
        )
        unknown_user = await authenticate_operator(session, "ghost", "VortemisAdmin2026!")
    assert bad_password is None
    assert unknown_user is None
