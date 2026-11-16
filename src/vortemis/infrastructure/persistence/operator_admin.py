from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vortemis.application.ports.driven.operator_admin import OperatorAdminPort
from vortemis.infrastructure.persistence.auth import hash_password
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import SocOperator


async def set_operator_password(
    session: AsyncSession,
    username: str,
    password: str,
    role: str | None = None,
) -> bool:
    operator = await session.scalar(
        select(SocOperator).where(SocOperator.username == username)
    )
    if operator is None:
        session.add(
            SocOperator(
                username=username,
                password_hash=hash_password(password),
                role=role or "analyst",
            )
        )
        return True
    operator.password_hash = hash_password(password)
    if role is not None:
        operator.role = role
    return False


class SqlOperatorAdmin(OperatorAdminPort):
    def __init__(self, database: SqlDatabase) -> None:
        self._database = database

    async def set_password(
        self, username: str, password: str, role: str | None = None
    ) -> bool:
        async with self._database.session() as session:
            created = await set_operator_password(
                session, username, password, role
            )
            await session.commit()
            return created
