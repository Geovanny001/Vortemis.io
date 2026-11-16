from typing import Protocol


class OperatorAdminPort(Protocol):
    async def set_password(
        self, username: str, password: str, role: str | None = None
    ) -> bool:
        ...
