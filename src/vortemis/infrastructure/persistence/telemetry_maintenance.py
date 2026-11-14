from pathlib import Path

from vortemis.application.ports.driven.telemetry_maintenance import (
    TelemetryMaintenancePort,
)
from vortemis.infrastructure.persistence.maintenance import purge_telemetry


class DatabaseTelemetryMaintenance(TelemetryMaintenancePort):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def purge(self, log_file: Path) -> None:
        await purge_telemetry(self._database_url, log_file)
