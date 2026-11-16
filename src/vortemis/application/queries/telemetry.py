from pathlib import Path

from vortemis.application.ports.driven.engine_metadata import EngineMetadataPort
from vortemis.application.ports.driven.flow_query import FlowQueryPort
from vortemis.application.ports.driven.operator_auth import OperatorAuthPort
from vortemis.application.ports.driven.telemetry_maintenance import (
    TelemetryMaintenancePort,
)
from vortemis.application.queries.dto import (
    FlowPage,
    ModelMetadata,
    OperatorIdentity,
    SourceAggregate,
    TimelinePoint,
)
from vortemis.application.queries.filters import FlowFilters


class TelemetryReadService:
    def __init__(
        self,
        flow_query: FlowQueryPort,
        auth: OperatorAuthPort,
        maintenance: TelemetryMaintenancePort,
        metadata: EngineMetadataPort,
    ) -> None:
        self._flow_query = flow_query
        self._auth = auth
        self._maintenance = maintenance
        self._metadata = metadata

    async def search_flows(
        self,
        filters: FlowFilters | None = None,
        limit: int = 500,
        cursor: str | None = None,
    ) -> FlowPage:
        return await self._flow_query.search_flows(
            filters=filters,
            limit=limit,
            cursor=cursor,
        )

    async def count_flows(self, filters: FlowFilters | None = None) -> int:
        return await self._flow_query.count_flows(filters=filters)

    async def count_anomalies(
        self, threshold: float, filters: FlowFilters | None = None
    ) -> int:
        return await self._flow_query.count_anomalies(
            threshold=threshold,
            filters=filters,
        )

    async def count_by_tactic(
        self, filters: FlowFilters | None = None
    ) -> dict[str, int]:
        return await self._flow_query.count_by_tactic(filters=filters)

    async def top_sources(
        self,
        threshold: float,
        filters: FlowFilters | None = None,
        limit: int = 10,
    ) -> list[SourceAggregate]:
        return await self._flow_query.top_sources(
            threshold=threshold,
            filters=filters,
            limit=limit,
        )

    async def timeline(
        self,
        threshold: float,
        bucket_seconds: int = 60,
        filters: FlowFilters | None = None,
    ) -> list[TimelinePoint]:
        return await self._flow_query.timeline(
            threshold=threshold,
            bucket_seconds=bucket_seconds,
            filters=filters,
        )

    async def model_metadata(self) -> ModelMetadata | None:
        return await self._metadata.load()

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> OperatorIdentity | None:
        return await self._auth.authenticate(username, password)

    async def purge(self, log_file: Path) -> None:
        await self._maintenance.purge(log_file)
