from doubles.in_memory_flow_repository import InMemoryFlowRepository
from vortemis.application.ports.driven.flow_repository import FlowRepositoryPort
from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp


def _make_flow(src: str, dst: str) -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress(src),
        dst_ip=IPAddress(dst),
        src_port=Port(12345),
        dst_port=Port(80),
        proto=Protocol.TCP,
        ts=Timestamp.from_epoch(1_700_000_000.0),
        orig_bytes=100,
        resp_bytes=200,
        duration=1.5,
    )


async def test_in_memory_repository_starts_empty() -> None:
    repo = InMemoryFlowRepository()
    assert repo.saved_flows == []


async def test_in_memory_repository_saves_and_retrieves_batch() -> None:
    repo = InMemoryFlowRepository()
    flows = [_make_flow("10.0.0.1", "10.0.0.2"), _make_flow("10.0.0.3", "10.0.0.4")]

    await repo.save_batch(flows)

    assert repo.saved_flows == flows


async def test_in_memory_repository_appends_across_batches() -> None:
    repo = InMemoryFlowRepository()

    await repo.save_batch([_make_flow("10.0.0.1", "10.0.0.2")])
    await repo.save_batch([_make_flow("10.0.0.5", "10.0.0.6")])

    assert len(repo.saved_flows) == 2


async def test_in_memory_repository_satisfies_flow_repository_port() -> None:
    repo = InMemoryFlowRepository()
    port: FlowRepositoryPort = repo

    await port.save_batch([_make_flow("10.0.0.1", "10.0.0.2")])

    assert len(repo.saved_flows) == 1
