from dataclasses import replace

import numpy
import pandas

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
        flows = self._attach_inter_arrival(flows)
        flows = self._attach_anomalies(flows)
        await self._repository.save_batch(flows)

    def _attach_inter_arrival(self, flows: list[NetworkFlow]) -> list[NetworkFlow]:
        frame = pandas.DataFrame(
            {
                "epoch": [flow.ts.value.timestamp() for flow in flows],
                "src": [flow.src_ip.value for flow in flows],
            }
        ).sort_values(["src", "epoch"])
        frame["iat_ms"] = frame.groupby("src")["epoch"].diff() * 1000.0
        iat_by_position = frame["iat_ms"].reindex(range(len(flows))).to_numpy()
        return [
            replace(
                flow,
                iat_ms=(
                    None
                    if pandas.isna(iat_by_position[index])
                    else float(iat_by_position[index])
                ),
            )
            for index, flow in enumerate(flows)
        ]

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
