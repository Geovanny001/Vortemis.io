from dataclasses import replace

import numpy

from vortemis.application.ports.driven.flow_repository import FlowRepositoryPort
from vortemis.application.ports.driving.raw_record import RawRecord
from vortemis.application.ports.driving.telemetry_source import TelemetrySourcePort
from vortemis.application.use_cases.bayesian_pytorch_engine import (
    BayesianPyTorchEngine,
    build_feature_vector,
    classify_mitre_tactic,
)
from vortemis.application.use_cases.mapper import ZeekFlowMapper
from vortemis.domain.entities.network_flow import NetworkFlow


class FlowNormalizerUseCase:
    def __init__(
        self,
        source: TelemetrySourcePort,
        repository: FlowRepositoryPort,
        engine: BayesianPyTorchEngine | None = None,
    ) -> None:
        self._source = source
        self._repository = repository
        self._mapper = ZeekFlowMapper()
        self._engine = engine
        self._last_timestamp_by_source: dict[str, float] = {}

    async def execute(self, batch_size: int = 1000) -> int:
        batch: list[RawRecord] = []
        inserted = 0
        async for record in self._source.stream():
            batch.append(record)
            if len(batch) >= batch_size:
                inserted += await self._flush(batch)
                batch = []
        if batch:
            inserted += await self._flush(batch)
        return inserted

    async def _flush(self, records: list[RawRecord]) -> int:
        flows = [
            flow
            for flow in (self._mapper.to_flow(record.data) for record in records)
            if flow is not None
        ]
        if not flows:
            return 0
        flows = self._attach_inter_arrival(flows)
        flows = self._attach_anomalies(flows)
        return await self._repository.save_batch(flows)

    def _attach_inter_arrival(self, flows: list[NetworkFlow]) -> list[NetworkFlow]:
        ordered_indices = sorted(
            range(len(flows)),
            key=lambda index: (
                flows[index].src_ip.value,
                flows[index].ts.value.timestamp(),
            ),
        )
        annotated: list[NetworkFlow | None] = [None] * len(flows)
        for index in ordered_indices:
            flow = flows[index]
            source = flow.src_ip.value
            epoch = flow.ts.value.timestamp()
            previous = self._last_timestamp_by_source.get(source)
            iat_ms = None if previous is None else (epoch - previous) * 1000.0
            if iat_ms is not None and iat_ms < 0:
                iat_ms = None
            self._last_timestamp_by_source[source] = (
                epoch if previous is None else max(previous, epoch)
            )
            annotated[index] = replace(flow, iat_ms=iat_ms)
        return [flow for flow in annotated if flow is not None]

    def _attach_anomalies(self, flows: list[NetworkFlow]) -> list[NetworkFlow]:
        if self._engine is None:
            return flows
        features = numpy.stack(
            [
                build_feature_vector(
                    iat_ms=flow.iat_ms,
                    orig_bytes=flow.orig_bytes,
                    resp_bytes=flow.resp_bytes,
                    duration=flow.duration,
                    conn_state=flow.conn_state,
                )
                for flow in flows
            ]
        )
        probabilities = self._engine.predict(features)
        annotated: list[NetworkFlow] = []
        for flow, probability in zip(flows, probabilities, strict=True):
            tactic = None
            if probability > self._engine.epsilon:
                tactic = classify_mitre_tactic(
                    conn_state=flow.conn_state,
                    src_ip=flow.src_ip.value,
                    dst_ip=flow.dst_ip.value,
                    dst_port=flow.dst_port.value,
                    orig_bytes=flow.orig_bytes,
                    resp_bytes=flow.resp_bytes,
                    iat_ms=flow.iat_ms,
                    duration=flow.duration,
                    pcr=_pcr(flow.orig_bytes, flow.resp_bytes),
                )
            annotated.append(
                replace(
                    flow,
                    anomaly_probability=float(probability),
                    mitre_tactic=tactic,
                )
            )
        return annotated


def _pcr(orig_bytes: int, resp_bytes: int) -> float:
    return (orig_bytes - resp_bytes) / (orig_bytes + resp_bytes + 1.0)
