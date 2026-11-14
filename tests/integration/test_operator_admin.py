from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from vortemis.infrastructure.persistence.auth import authenticate_operator
from vortemis.infrastructure.persistence.models import Base
from vortemis.infrastructure.persistence.operator_admin import set_operator_password


async def test_set_operator_password_creates_and_rotates() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        created = await set_operator_password(
            session, "new_admin", "first-password", "admin"
        )
        await session.commit()
        operator = await authenticate_operator(session, "new_admin", "first-password")

    assert created is True
    assert operator is not None
    assert operator.role == "admin"

    async with session_factory() as session:
        created = await set_operator_password(
            session, "new_admin", "second-password", "analyst"
        )
        await session.commit()
        old_password = await authenticate_operator(session, "new_admin", "first-password")
        new_password = await authenticate_operator(session, "new_admin", "second-password")

    assert created is False
    assert old_password is None
    assert new_password is not None
    assert new_password.role == "analyst"

    await engine.dispose()
