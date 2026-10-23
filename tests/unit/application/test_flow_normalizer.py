from doubles.fake_telemetry_source import FakeTelemetrySource
from doubles.in_memory_flow_repository import InMemoryFlowRepository
from vortemis.application.ports.driving.raw_record import RawRecord
from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.domain.value_objects.protocol import Protocol


def _row(ts: str, src_ip: str) -> dict[str, str]:
    return {
        "ts": ts,
        "id.orig_h": src_ip,
        "id.orig_p": "12345",
        "id.resp_h": "10.0.0.2",
        "id.resp_p": "443",
        "proto": "tcp",
        "orig_bytes": "100",
        "resp_bytes": "200",
        "duration": "1.5",
        "conn_state": "SF",
    }


def _record(ts: str, src_ip: str, line: int) -> RawRecord:
    return RawRecord(data=_row(ts, src_ip), source_line=line)


async def test_flow_normalizer_computes_iat_and_saves_flows() -> None:
    source = FakeTelemetrySource(
        [
            _record("10.0", "10.0.0.1", 1),
            _record("5.0", "10.0.0.3", 2),
            _record("20.0", "10.0.0.5", 3),
        ]
    )
    repository = InMemoryFlowRepository()
    use_case = FlowNormalizerUseCase(source=source, repository=repository)

    await use_case.execute()

    saved = sorted(
        repository.saved_flows, key=lambda flow: flow.ts.value.timestamp()
    )
    assert [flow.src_ip.value for flow in saved] == [
        "10.0.0.3",
        "10.0.0.1",
        "10.0.0.5",
    ]
    assert [flow.iat_ms for flow in saved] == [0.0, 5000.0, 10000.0]
    assert all(flow.proto is Protocol.TCP for flow in saved)
    assert saved[1].orig_bytes == 100
    assert saved[1].resp_bytes == 200
    assert saved[1].duration == 1.5
    assert saved[1].conn_state == "SF"


async def test_flow_normalizer_skips_invalid_records() -> None:
    source = FakeTelemetrySource(
        [
            _record("5.0", "10.0.0.1", 1),
            _record("10.0", "999.999.999.999", 2),
            _record("15.0", "10.0.0.3", 3),
        ]
    )
    repository = InMemoryFlowRepository()
    use_case = FlowNormalizerUseCase(source=source, repository=repository)

    await use_case.execute()

    assert len(repository.saved_flows) == 2
    assert all(
        flow.src_ip.value != "999.999.999.999" for flow in repository.saved_flows
    )


async def test_flow_normalizer_processes_multiple_batches() -> None:
    records = [
        _record(str(index), f"10.0.0.{index}", index) for index in range(1, 6)
    ]
    source = FakeTelemetrySource(records)
    repository = InMemoryFlowRepository()
    use_case = FlowNormalizerUseCase(source=source, repository=repository)

    await use_case.execute(batch_size=2)

    assert len(repository.saved_flows) == 5
