from pathlib import Path

from vortemis.application.ports.driven.flow_query import FlowQueryPort
from vortemis.application.ports.driven.operator_auth import OperatorAuthPort
from vortemis.application.ports.driven.telemetry_maintenance import (
    TelemetryMaintenancePort,
)
from vortemis.application.queries.dto import FlowRecord, OperatorIdentity


class TelemetryReadService:
    def __init__(
        self,
        flow_query: FlowQueryPort,
        auth: OperatorAuthPort,
        maintenance: TelemetryMaintenancePort,
    ) -> None:
        self._flow_query = flow_query
        self._auth = auth
        self._maintenance = maintenance

    async def load_flows(self, limit: int = 20000) -> list[FlowRecord]:
        return await self._flow_query.load_flows(limit)

    async def count_flows(self) -> int:
        return await self._flow_query.count_flows()

    async def count_anomalies(self, threshold: float) -> int:
        return await self._flow_query.count_anomalies(threshold)

    async def count_by_tactic(self) -> dict[str, int]:
        return await self._flow_query.count_by_tactic()

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> OperatorIdentity | None:
        return await self._auth.authenticate(username, password)

    async def purge(self, log_file: Path) -> None:
        await self._maintenance.purge(log_file)
