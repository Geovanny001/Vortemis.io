from sqlalchemy import func, select

from vortemis.application.ports.driven.flow_query import FlowQueryPort
from vortemis.application.queries.dto import FlowRecord
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
)
from vortemis.infrastructure.persistence.session import session_scope


class SqlFlowQuery(FlowQueryPort):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def load_flows(self, limit: int) -> list[FlowRecord]:
        async with session_scope(self._database_url) as session:
            rows = (
                await session.execute(
                    select(
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
                    .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
                    .outerjoin(
                        DimConnState,
                        FactNetworkFlow.conn_state_id == DimConnState.id,
                    )
                    .outerjoin(
                        DimMitreTactic,
                        FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
                    )
                    .order_by(FactNetworkFlow.ts.desc())
                    .limit(limit)
                )
            ).all()
        return [
            FlowRecord(
                ts=row[0],
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
            for row in rows
        ]

    async def count_flows(self) -> int:
        async with session_scope(self._database_url) as session:
            value = await session.scalar(
                select(func.count()).select_from(FactNetworkFlow)
            )
        return int(value or 0)

    async def count_anomalies(self, threshold: float) -> int:
        async with session_scope(self._database_url) as session:
            value = await session.scalar(
                select(func.count())
                .select_from(FactNetworkFlow)
                .where(FactNetworkFlow.anomaly_probability >= threshold)
            )
        return int(value or 0)

    async def count_by_tactic(self) -> dict[str, int]:
        async with session_scope(self._database_url) as session:
            rows = (
                await session.execute(
                    select(DimMitreTactic.mitre_id, func.count(FactNetworkFlow.id))
                    .join(
                        FactNetworkFlow,
                        FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
                    )
                    .group_by(DimMitreTactic.mitre_id)
                )
            ).all()
        return {str(row[0]): int(row[1]) for row in rows}
