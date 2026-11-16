from typing import Protocol


class LoginThrottlePort(Protocol):
    async def allow(self, username: str) -> bool:
        ...

    async def remaining_seconds(self, username: str) -> float:
        ...

    async def register_failure(self, username: str) -> None:
        ...

    async def register_success(self, username: str) -> None:
        ...
