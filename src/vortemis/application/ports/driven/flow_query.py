from typing import Protocol

from vortemis.application.queries.dto import FlowRecord


class FlowQueryPort(Protocol):
    async def load_flows(self, limit: int) -> list[FlowRecord]:
        ...

    async def count_flows(self) -> int:
        ...

    async def count_anomalies(self, threshold: float) -> int:
        ...

    async def count_by_tactic(self) -> dict[str, int]:
        ...
