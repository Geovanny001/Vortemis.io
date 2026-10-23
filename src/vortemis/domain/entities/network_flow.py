from dataclasses import dataclass, field
from uuid import UUID, uuid4

from vortemis.domain.errors import InvalidFlowMetricError
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp


@dataclass(frozen=True, slots=True)
class NetworkFlow:
    src_ip: IPAddress
    dst_ip: IPAddress
    src_port: Port
    dst_port: Port
    proto: Protocol
    ts: Timestamp
    orig_bytes: int
    resp_bytes: int
    duration: float
    iat_ms: float | None = None
    conn_state: str | None = None
    flow_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.orig_bytes < 0 or self.resp_bytes < 0:
            raise InvalidFlowMetricError("byte metrics cannot be negative")
        if self.duration < 0:
            raise InvalidFlowMetricError("duration cannot be negative")
        if self.iat_ms is not None and self.iat_ms < 0:
            raise InvalidFlowMetricError("iat_ms cannot be negative")
