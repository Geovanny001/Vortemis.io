from collections.abc import AsyncIterator, Sequence

from vortemis.application.ports.driving.raw_record import RawRecord


class FakeTelemetrySource:
    def __init__(self, records: Sequence[RawRecord]) -> None:
        self._records = list(records)

    async def stream(self) -> AsyncIterator[RawRecord]:
        for record in self._records:
            yield record
