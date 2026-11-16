from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from vortemis.application.ports.driven.login_throttle import LoginThrottlePort
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import LoginAttempt

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW = timedelta(minutes=5)
DEFAULT_LOCKOUT = timedelta(minutes=5)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SqlLoginThrottle(LoginThrottlePort):
    def __init__(
        self,
        database: SqlDatabase,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        window: timedelta = DEFAULT_WINDOW,
        lockout: timedelta = DEFAULT_LOCKOUT,
    ) -> None:
        self._database = database
        self._max_attempts = max_attempts
        self._window = window
        self._lockout = lockout

    async def _recent(
        self, username: str, now: datetime
    ) -> tuple[int, datetime | None]:
        threshold = now - self._window
        async with self._database.session() as session:
            await session.execute(
                delete(LoginAttempt).where(
                    LoginAttempt.username == username,
                    LoginAttempt.attempted_at < threshold,
                )
            )
            attempts = (
                await session.execute(
                    select(LoginAttempt.attempted_at).where(
                        LoginAttempt.username == username
                    )
                )
            ).scalars()
            timestamps = [_aware(value) for value in attempts]
            await session.commit()
        if not timestamps:
            return 0, None
        return len(timestamps), max(timestamps)

    async def allow(self, username: str) -> bool:
        now = datetime.now(UTC)
        failures, last = await self._recent(username, now)
        if failures < self._max_attempts:
            return True
        if last is None:
            return True
        return last + self._lockout <= now

    async def remaining_seconds(self, username: str) -> float:
        now = datetime.now(UTC)
        failures, last = await self._recent(username, now)
        if failures < self._max_attempts or last is None:
            return 0.0
        remaining = (last + self._lockout - now).total_seconds()
        return max(0.0, remaining)

    async def register_failure(self, username: str) -> None:
        async with self._database.session() as session:
            session.add(
                LoginAttempt(
                    username=username, attempted_at=datetime.now(UTC)
                )
            )
            await session.commit()

    async def register_success(self, username: str) -> None:
        async with self._database.session() as session:
            await session.execute(
                delete(LoginAttempt).where(
                    LoginAttempt.username == username
                )
            )
            await session.commit()
