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
class OperatorIdentity:
    username: str
    role: str
