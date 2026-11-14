import hashlib
import hmac
import os
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vortemis.infrastructure.persistence.models import SocOperator

_PBKDF2_ITERATIONS = 100_000


def _default_operators() -> list[tuple[str, str, str]]:
    return [
        (
            os.getenv("VORTEMIS_ADMIN_USERNAME", "admin_carles"),
            os.getenv("VORTEMIS_ADMIN_PASSWORD", "VortemisAdmin2026!"),
            "admin",
        ),
        (
            os.getenv("VORTEMIS_ANALYST_USERNAME", "soc_analyst"),
            os.getenv("VORTEMIS_ANALYST_PASSWORD", "VortemisAnalyst2026!"),
            "analyst",
        ),
    ]


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    ).hex()
    return f"{salt}${_PBKDF2_ITERATIONS}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, iterations, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(digest, expected)


async def seed_default_operators(session: AsyncSession) -> None:
    result = await session.execute(select(SocOperator.username))
    existing = set(result.scalars())
    missing = [
        SocOperator(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        for username, password, role in _default_operators()
        if username not in existing
    ]
    if missing:
        session.add_all(missing)


async def authenticate_operator(
    session: AsyncSession,
    username: str,
    password: str,
) -> SocOperator | None:
    operator = await session.scalar(
        select(SocOperator).where(SocOperator.username == username)
    )
    if operator is None or not verify_password(password, operator.password_hash):
        return None
    return operator
