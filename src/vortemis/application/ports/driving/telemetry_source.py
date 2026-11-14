from collections.abc import AsyncIterator
from typing import Protocol

from vortemis.application.ports.driving.raw_record import RawRecord


class TelemetrySourcePort(Protocol):
    @property
    def position(self) -> int:
        ...

    def stream(self) -> AsyncIterator[RawRecord]:
        ...
