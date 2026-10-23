from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vortemis.application.ports.driven.flow_repository import FlowRepositoryPort
from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimProtocol,
    FactNetworkFlow,
)


class PostgresFlowRepository(FlowRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_batch(self, flows: list[NetworkFlow]) -> None:
        async with self._session_factory() as session:
            protocol_ids = await self._ensure_protocols(session, flows)
            conn_state_ids = await self._ensure_conn_states(session, flows)
            session.add_all(
                self._to_fact_row(
                    flow,
                    protocol_ids[flow.proto.value],
                    conn_state_ids.get(flow.conn_state),
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

    def _to_fact_row(
        self,
        flow: NetworkFlow,
        protocol_id: int,
        conn_state_id: int | None,
    ) -> FactNetworkFlow:
        return FactNetworkFlow(
            flow_id=str(flow.flow_id),
            src_ip=flow.src_ip.value,
            dst_ip=flow.dst_ip.value,
            src_port=flow.src_port.value,
            dst_port=flow.dst_port.value,
            protocol_id=protocol_id,
            conn_state_id=conn_state_id,
            ts=flow.ts.value,
            orig_bytes=flow.orig_bytes,
            resp_bytes=flow.resp_bytes,
            duration=flow.duration,
            iat_ms=flow.iat_ms,
        )
