from typing import Protocol

from vortemis.application.queries.dto import (
    FlowPage,
    SourceAggregate,
    TimelinePoint,
)
from vortemis.application.queries.filters import FlowFilters


class FlowQueryPort(Protocol):
    async def search_flows(
        self,
        filters: FlowFilters | None = None,
        limit: int = 500,
        cursor: str | None = None,
    ) -> FlowPage:
        ...

    async def count_flows(self, filters: FlowFilters | None = None) -> int:
        ...

    async def count_anomalies(
        self, threshold: float, filters: FlowFilters | None = None
    ) -> int:
        ...

    async def count_by_tactic(
        self, filters: FlowFilters | None = None
    ) -> dict[str, int]:
        ...

    async def top_sources(
        self,
        threshold: float,
        filters: FlowFilters | None = None,
        limit: int = 10,
    ) -> list[SourceAggregate]:
        ...

    async def timeline(
        self,
        threshold: float,
        bucket_seconds: int = 60,
        filters: FlowFilters | None = None,
    ) -> list[TimelinePoint]:
        ...
