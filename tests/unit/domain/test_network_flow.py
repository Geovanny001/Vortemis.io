from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.errors import InvalidFlowMetricError
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp


def _flow(**overrides: object) -> NetworkFlow:
    params: dict[str, object] = {
        "src_ip": IPAddress("10.0.0.1"),
        "dst_ip": IPAddress("10.0.0.2"),
        "src_port": Port(12345),
        "dst_port": Port(80),
        "proto": Protocol.TCP,
        "ts": Timestamp.from_epoch(1_700_000_000.0),
        "orig_bytes": 100,
        "resp_bytes": 200,
        "duration": 1.5,
    }
    params.update(overrides)
    return NetworkFlow(**params)


def test_network_flow_builds_with_valid_fields() -> None:
    flow = _flow()
    assert flow.src_ip.value == "10.0.0.1"
    assert flow.dst_ip.value == "10.0.0.2"
    assert flow.src_port.value == 12345
    assert flow.dst_port.value == 80
    assert flow.proto is Protocol.TCP
    assert flow.orig_bytes == 100
    assert flow.resp_bytes == 200
    assert flow.duration == 1.5


def test_network_flow_generates_flow_id_by_default() -> None:
    assert isinstance(_flow().flow_id, UUID)


def test_network_flow_accepts_explicit_flow_id() -> None:
    flow_id = UUID("12345678-1234-5678-1234-567812345678")
    assert _flow(flow_id=flow_id).flow_id == flow_id


def test_network_flow_is_immutable() -> None:
    flow = _flow()
    with pytest.raises(FrozenInstanceError):
        flow.orig_bytes = 999


def test_negative_orig_bytes_raises() -> None:
    with pytest.raises(InvalidFlowMetricError):
        _flow(orig_bytes=-1)


def test_negative_resp_bytes_raises() -> None:
    with pytest.raises(InvalidFlowMetricError):
        _flow(resp_bytes=-1)


def test_negative_duration_raises() -> None:
    with pytest.raises(InvalidFlowMetricError):
        _flow(duration=-0.1)


def test_negative_iat_ms_raises() -> None:
    with pytest.raises(InvalidFlowMetricError):
        _flow(iat_ms=-1.0)
