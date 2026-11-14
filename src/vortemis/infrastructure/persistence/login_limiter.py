import time
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_LOCKOUT_SECONDS = 300.0
DEFAULT_WINDOW_SECONDS = 300.0


@dataclass(slots=True)
class _AttemptState:
    failures: int = 0
    first_failure: float | None = None
    locked_until: float | None = None


class LoginLimiter:
    def __init__(
        self,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lockout_seconds: float = DEFAULT_LOCKOUT_SECONDS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._lockout_seconds = lockout_seconds
        self._window_seconds = window_seconds
        self._clock = clock
        self._states: dict[str, _AttemptState] = {}

    def is_locked(self, username: str) -> bool:
        state = self._states.get(username)
        if state is None:
            return False
        now = self._clock()
        if state.locked_until is not None:
            if state.locked_until > now:
                return True
            self._states.pop(username, None)
            return False
        if (
            state.first_failure is not None
            and now - state.first_failure > self._window_seconds
        ):
            self._states.pop(username, None)
            return False
        return False

    def remaining_seconds(self, username: str) -> float:
        state = self._states.get(username)
        if state is None or state.locked_until is None:
            return 0.0
        return max(0.0, state.locked_until - self._clock())

    def record_failure(self, username: str) -> None:
        now = self._clock()
        state = self._states.setdefault(username, _AttemptState())
        if (
            state.first_failure is None
            or now - state.first_failure > self._window_seconds
        ):
            state.failures = 0
            state.first_failure = now
        state.failures += 1
        if state.failures >= self._max_attempts:
            state.locked_until = now + self._lockout_seconds

    def record_success(self, username: str) -> None:
        self._states.pop(username, None)

    def allow(self, username: str) -> bool:
        return not self.is_locked(username)
