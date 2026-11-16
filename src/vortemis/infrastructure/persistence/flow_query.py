from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    Integer,
    Select,
    and_,
    case,
    cast,
    func,
    or_,
    select,
)
from sqlalchemy.engine import Row

from vortemis.application.errors import InvalidQueryError
from vortemis.application.ports.driven.flow_query import FlowQueryPort
from vortemis.application.queries.dto import (
    FlowPage,
    FlowRecord,
    SourceAggregate,
    TimelinePoint,
)
from vortemis.application.queries.filters import FlowFilters
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
)

_CURSOR_SEPARATOR = "|"
_FLOW_COLUMNS = (
    FactNetworkFlow.ts,
    FactNetworkFlow.flow_id,
    FactNetworkFlow.src_ip,
    FactNetworkFlow.dst_ip,
    FactNetworkFlow.src_port,
    FactNetworkFlow.dst_port,
    DimProtocol.name,
    DimConnState.name,
    FactNetworkFlow.iat_ms,
    FactNetworkFlow.orig_bytes,
    FactNetworkFlow.resp_bytes,
    FactNetworkFlow.duration,
    FactNetworkFlow.anomaly_probability,
    FactNetworkFlow.is_anomaly,
    DimMitreTactic.mitre_id,
)


class SqlFlowQuery(FlowQueryPort):
    def __init__(self, database: SqlDatabase) -> None:
        self._database = database

    async def search_flows(
        self,
        filters: FlowFilters | None = None,
        limit: int = 500,
        cursor: str | None = None,
    ) -> FlowPage:
        if limit <= 0:
            raise InvalidQueryError("limit must be positive")
        conditions = _conditions(filters)
        if cursor is not None:
            cursor_ts, cursor_flow = _decode_cursor(cursor)
            conditions.append(
                or_(
                    FactNetworkFlow.ts < cursor_ts,
                    and_(
                        FactNetworkFlow.ts == cursor_ts,
                        FactNetworkFlow.flow_id < cursor_flow,
                    ),
                )
            )
        statement = (
            _joined(_FLOW_COLUMNS)
            .where(*conditions)
            .order_by(FactNetworkFlow.ts.desc(), FactNetworkFlow.flow_id.desc())
            .limit(limit + 1)
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).all()
        records = [_to_record(row) for row in rows[:limit]]
        next_cursor = (
            _encode_cursor(records[-1]) if len(rows) > limit else None
        )
        return FlowPage(records=records, next_cursor=next_cursor)

    async def count_flows(self, filters: FlowFilters | None = None) -> int:
        statement = select(func.count()).select_from(
            _joined([FactNetworkFlow.id])
            .where(*_conditions(filters))
            .subquery()
        )
        async with self._database.session() as session:
            value = await session.scalar(statement)
        return int(value or 0)

    async def count_anomalies(
        self, threshold: float, filters: FlowFilters | None = None
    ) -> int:
        _check_probability(threshold)
        conditions = [
            *_conditions(filters),
            FactNetworkFlow.anomaly_probability >= threshold,
        ]
        statement = select(func.count()).select_from(
            _joined([FactNetworkFlow.id]).where(*conditions).subquery()
        )
        async with self._database.session() as session:
            value = await session.scalar(statement)
        return int(value or 0)

    async def count_by_tactic(
        self, filters: FlowFilters | None = None
    ) -> dict[str, int]:
        statement = (
            select(DimMitreTactic.mitre_id, func.count(FactNetworkFlow.id))
            .join(
                FactNetworkFlow,
                FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
            )
            .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
            .where(*_conditions(filters))
            .group_by(DimMitreTactic.mitre_id)
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).all()
        return {str(row[0]): int(row[1]) for row in rows}

    async def top_sources(
        self,
        threshold: float,
        filters: FlowFilters | None = None,
        limit: int = 10,
    ) -> list[SourceAggregate]:
        _check_probability(threshold)
        if limit <= 0:
            raise InvalidQueryError("limit must be positive")
        anomalies = _anomaly_count(threshold)
        statement = (
            _joined(
                [
                    FactNetworkFlow.src_ip,
                    func.count(FactNetworkFlow.id),
                    anomalies,
                ]
            )
            .where(*_conditions(filters))
            .group_by(FactNetworkFlow.src_ip)
            .order_by(func.count(FactNetworkFlow.id).desc())
            .limit(limit)
        )
        async with self._database.session() as session:
            rows = (await session.execute(statement)).all()
        return [
            SourceAggregate(
                src_ip=str(row[0]),
                flows=int(row[1]),
                anomalies=int(row[2] or 0),
            )
            for row in rows
        ]

    async def timeline(
        self,
        threshold: float,
        bucket_seconds: int = 60,
        filters: FlowFilters | None = None,
    ) -> list[TimelinePoint]:
        _check_probability(threshold)
        if bucket_seconds <= 0:
            raise InvalidQueryError("bucket_seconds must be positive")
        async with self._database.session() as session:
            bucket = _bucket_expression(
                session.get_bind().dialect.name, bucket_seconds
            )
            anomalies = _anomaly_count(threshold)
            statement = (
                _joined(
                    [bucket, func.count(FactNetworkFlow.id), anomalies]
                )
                .where(*_conditions(filters))
                .group_by(bucket)
                .order_by(bucket)
            )
            rows = (await session.execute(statement)).all()
        return [
            TimelinePoint(
                bucket_start=datetime.fromtimestamp(int(row[0]), tz=UTC),
                flows=int(row[1]),
                anomalies=int(row[2] or 0),
            )
            for row in rows
        ]


def _joined(columns: Sequence[Any]) -> Select[Any]:
    return (
        select(*columns)
        .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
        .outerjoin(
            DimConnState,
            FactNetworkFlow.conn_state_id == DimConnState.id,
        )
        .outerjoin(
            DimMitreTactic,
            FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
        )
    )


def _conditions(filters: FlowFilters | None) -> list[Any]:
    if filters is None:
        return []
    conditions: list[Any] = []
    if filters.since is not None:
        conditions.append(FactNetworkFlow.ts >= filters.since)
    if filters.until is not None:
        conditions.append(FactNetworkFlow.ts <= filters.until)
    if filters.src_ip is not None:
        conditions.append(FactNetworkFlow.src_ip == filters.src_ip)
    if filters.dst_ip is not None:
        conditions.append(FactNetworkFlow.dst_ip == filters.dst_ip)
    if filters.src_port is not None:
        conditions.append(FactNetworkFlow.src_port == filters.src_port)
    if filters.dst_port is not None:
        conditions.append(FactNetworkFlow.dst_port == filters.dst_port)
    if filters.protocol is not None:
        conditions.append(DimProtocol.name == filters.protocol)
    if filters.tactic is not None:
        conditions.append(DimMitreTactic.mitre_id == filters.tactic)
    if filters.min_probability is not None:
        conditions.append(
            FactNetworkFlow.anomaly_probability >= filters.min_probability
        )
    return conditions


def _anomaly_count(threshold: float) -> ColumnElement[int]:
    return func.coalesce(
        func.sum(
            case((FactNetworkFlow.anomaly_probability >= threshold, 1), else_=0)
        ),
        0,
    )


def _bucket_expression(dialect: str, bucket_seconds: int) -> ColumnElement[int]:
    if dialect == "postgresql":
        epoch = func.extract("epoch", FactNetworkFlow.ts)
        bucketed = func.floor(epoch / bucket_seconds) * bucket_seconds
        return cast(bucketed, BigInteger)
    epoch = cast(func.strftime("%s", FactNetworkFlow.ts), Integer)
    truncated = cast(epoch / bucket_seconds, Integer)
    return cast(truncated * bucket_seconds, Integer)


def _encode_cursor(record: FlowRecord) -> str:
    return f"{record.ts.isoformat()}{_CURSOR_SEPARATOR}{record.flow_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw_ts, separator, flow_id = cursor.partition(_CURSOR_SEPARATOR)
    if not separator or not flow_id:
        raise InvalidQueryError(f"invalid cursor: {cursor!r}")
    try:
        timestamp = datetime.fromisoformat(raw_ts)
    except ValueError as exc:
        raise InvalidQueryError(f"invalid cursor: {cursor!r}") from exc
    if timestamp.tzinfo is None:
        raise InvalidQueryError(f"invalid cursor: {cursor!r}")
    return timestamp, flow_id


def _check_probability(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise InvalidQueryError("threshold must be within [0, 1]")


def _to_record(row: Row[Any]) -> FlowRecord:
    timestamp = row[0] if row[0].tzinfo is not None else row[0].replace(tzinfo=UTC)
    return FlowRecord(
        ts=timestamp,
        flow_id=row[1],
        src_ip=row[2],
        dst_ip=row[3],
        src_port=row[4],
        dst_port=row[5],
        protocol=row[6],
        conn_state=row[7],
        iat_ms=row[8],
        orig_bytes=row[9],
        resp_bytes=row[10],
        duration=row[11],
        anomaly_probability=row[12],
        is_anomaly=row[13],
        mitre_tactic=row[14],
    )
