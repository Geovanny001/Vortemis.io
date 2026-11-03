from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vortemis.application.ports.driven.flow_repository import FlowRepositoryPort
from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
)

MITRE_TACTICS = {
    "TA0010": "Exfiltration",
    "TA0008": "Lateral Movement",
    "TA0011": "Command and Control",
    "TA0040": "Impact",
    "TA0043": "Reconnaissance",
}

DEFAULT_EPSILON = 0.70


class PostgresFlowRepository(FlowRepositoryPort):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        epsilon: float = DEFAULT_EPSILON,
    ) -> None:
        self._session_factory = session_factory
        self._epsilon = epsilon

    async def save_batch(self, flows: list[NetworkFlow]) -> None:
        async with self._session_factory() as session:
            protocol_ids = await self._ensure_protocols(session, flows)
            conn_state_ids = await self._ensure_conn_states(session, flows)
            tactic_ids = await self._ensure_mitre_tactics(session)
            session.add_all(
                self._to_fact_row(
                    flow,
                    protocol_ids[flow.proto.value],
                    conn_state_ids.get(flow.conn_state),
                    tactic_ids,
                )
                for flow in flows
            )
            await session.commit()

    async def _ensure_protocols(
        self, session: AsyncSession, flows: list[NetworkFlow]
    ) -> dict[str, int]:
        names = {flow.proto.value for flow in flows}
        if not names:
            return {}
        result = await session.execute(
            select(DimProtocol).where(DimProtocol.name.in_(names))
        )
        ids = {row.name: row.id for row in result.scalars()}
        missing = [DimProtocol(name=name) for name in names if name not in ids]
        if missing:
            session.add_all(missing)
            await session.flush()
            ids.update({row.name: row.id for row in missing})
        return ids

    async def _ensure_conn_states(
        self, session: AsyncSession, flows: list[NetworkFlow]
    ) -> dict[str, int]:
        names = {flow.conn_state for flow in flows if flow.conn_state is not None}
        if not names:
            return {}
        result = await session.execute(
            select(DimConnState).where(DimConnState.name.in_(names))
        )
        ids = {row.name: row.id for row in result.scalars()}
        missing = [DimConnState(name=name) for name in names if name not in ids]
        if missing:
            session.add_all(missing)
            await session.flush()
            ids.update({row.name: row.id for row in missing})
        return ids

    async def _ensure_mitre_tactics(self, session: AsyncSession) -> dict[str, int]:
        result = await session.execute(select(DimMitreTactic))
        ids = {row.mitre_id: row.tactic_id for row in result.scalars()}
        missing = [
            DimMitreTactic(mitre_id=mitre_id, tactic_name=tactic_name)
            for mitre_id, tactic_name in MITRE_TACTICS.items()
            if mitre_id not in ids
        ]
        if missing:
            session.add_all(missing)
            await session.flush()
            ids.update({row.mitre_id: row.tactic_id for row in missing})
        return ids

    def _to_fact_row(
        self,
        flow: NetworkFlow,
        protocol_id: int,
        conn_state_id: int | None,
        tactic_ids: dict[str, int],
    ) -> FactNetworkFlow:
        tactic_id = tactic_ids.get(flow.mitre_tactic) if flow.mitre_tactic else None
        return FactNetworkFlow(
            flow_id=str(flow.flow_id),
            src_ip=flow.src_ip.value,
            dst_ip=flow.dst_ip.value,
            src_port=flow.src_port.value,
            dst_port=flow.dst_port.value,
            protocol_id=protocol_id,
            conn_state_id=conn_state_id,
            tactic_id=tactic_id,
            ts=flow.ts.value,
            orig_bytes=flow.orig_bytes,
            resp_bytes=flow.resp_bytes,
            duration=flow.duration,
            iat_ms=flow.iat_ms,
            anomaly_probability=flow.anomaly_probability,
            is_anomaly=flow.anomaly_probability >= self._epsilon,
        )
