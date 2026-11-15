from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FlowRecord:
    ts: datetime
    flow_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    conn_state: str | None
    iat_ms: float | None
    orig_bytes: int
    resp_bytes: int
    duration: float
    anomaly_probability: float
    is_anomaly: bool
    mitre_tactic: str | None


@dataclass(frozen=True, slots=True)
class FlowPage:
    records: list[FlowRecord]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class SourceAggregate:
    src_ip: str
    flows: int
    anomalies: int


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    bucket_start: datetime
    flows: int
    anomalies: int


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    architecture: str
    feature_dim: int
    tau: float
    mean: tuple[float, ...]
    std: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    username: str
    role: str
