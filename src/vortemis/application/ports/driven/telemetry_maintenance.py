from pathlib import Path
from typing import Protocol


class TelemetryMaintenancePort(Protocol):
    async def purge(self, log_file: Path) -> None:
        ...
