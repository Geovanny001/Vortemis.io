from typing import Protocol

from vortemis.domain.entities.network_flow import NetworkFlow


class FlowRepositoryPort(Protocol):
    async def save_batch(self, flows: list[NetworkFlow]) -> None:
        ...
