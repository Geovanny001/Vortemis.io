from dataclasses import replace

import numpy
import pandas

from vortemis.application.ports.driven.flow_repository import FlowRepositoryPort
from vortemis.application.ports.driving.raw_record import RawRecord
from vortemis.application.ports.driving.telemetry_source import TelemetrySourcePort
from vortemis.application.use_cases.mapper import ZeekFlowMapper
from vortemis.domain.entities.network_flow import NetworkFlow


class FlowNormalizerUseCase:
    def __init__(self, source: TelemetrySourcePort, repository: FlowRepositoryPort) -> None:
        self._source = source
        self._repository = repository
        self._mapper = ZeekFlowMapper()

    async def execute(self, batch_size: int = 1000) -> None:
        batch: list[RawRecord] = []
        async for record in self._source.stream():
            batch.append(record)
            if len(batch) >= batch_size:
                await self._flush(batch)
                batch = []
        if batch:
            await self._flush(batch)

    async def _flush(self, records: list[RawRecord]) -> None:
        flows = [
            flow
            for flow in (self._mapper.to_flow(record.data) for record in records)
            if flow is not None
        ]
        if not flows:
            return
        await self._repository.save_batch(self._attach_inter_arrival(flows))

    def _attach_inter_arrival(self, flows: list[NetworkFlow]) -> list[NetworkFlow]:
        frame = pandas.DataFrame(
            {"epoch": [flow.ts.value.timestamp() for flow in flows]}
        )
        epochs = frame["epoch"].to_numpy()
        order = numpy.argsort(epochs)
        iat_ms = numpy.diff(epochs[order], prepend=epochs[order][0]) * 1000.0
        by_position = numpy.empty(len(flows))
        by_position[order] = iat_ms
        return [
            replace(flow, iat_ms=float(by_position[index]))
            for index, flow in enumerate(flows)
        ]
