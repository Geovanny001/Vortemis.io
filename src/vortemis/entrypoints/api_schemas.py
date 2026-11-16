from datetime import datetime

from pydantic import BaseModel, ConfigDict

from vortemis.application.queries.dto import (
    FlowPage,
    ModelMetadata,
    SourceAggregate,
    TimelinePoint,
)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class IdentityResponse(BaseModel):
    username: str
    role: str


class FlowRecordSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class FlowPageSchema(BaseModel):
    records: list[FlowRecordSchema]
    next_cursor: str | None


class SourceAggregateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    src_ip: str
    flows: int
    anomalies: int


class TimelinePointSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bucket_start: datetime
    flows: int
    anomalies: int


class ModelMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    architecture: str
    feature_dim: int
    tau: float
    mean: tuple[float, ...]
    std: tuple[float, ...]


class SummaryResponse(BaseModel):
    total_flows: int
    anomalies: int
    by_tactic: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    database: str


def to_flow_page(page: FlowPage) -> FlowPageSchema:
    return FlowPageSchema(
        records=[
            FlowRecordSchema.model_validate(record) for record in page.records
        ],
        next_cursor=page.next_cursor,
    )


def to_source(source: SourceAggregate) -> SourceAggregateSchema:
    return SourceAggregateSchema.model_validate(source)


def to_timeline(point: TimelinePoint) -> TimelinePointSchema:
    return TimelinePointSchema.model_validate(point)


def to_metadata(metadata: ModelMetadata) -> ModelMetadataSchema:
    return ModelMetadataSchema.model_validate(metadata)
