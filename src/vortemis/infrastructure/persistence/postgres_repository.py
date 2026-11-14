from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vortemis.application.mitre import MITRE_TACTICS
from vortemis.application.ports.driven.flow_repository import FlowRepositoryPort
from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
)

DEFAULT_EPSILON = 0.70
_INSERT_CHUNK = 1000


class PostgresFlowRepository(FlowRepositoryPort):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        epsilon: float = DEFAULT_EPSILON,
    ) -> None:
        self._session_factory = session_factory
        self._epsilon = epsilon
        self._protocol_ids: dict[str, int] = {}
        self._conn_state_ids: dict[str, int] = {}
        self._tactic_ids: dict[str, int] = {}

    async def save_batch(self, flows: list[NetworkFlow]) -> int:
        if not flows:
            return 0
        async with self._session_factory() as session:
            protocol_ids = await self._ensure_protocols(session, flows)
            conn_state_ids = await self._ensure_conn_states(session, flows)
            tactic_ids = await self._ensure_mitre_tactics(session)
            values = [
                self._to_fact_values(
                    flow,
                    protocol_ids[flow.proto.value],
                    conn_state_ids.get(flow.conn_state),
                    tactic_ids,
                )
                for flow in flows
            ]
            inserted = await self._insert_values(session, values)
            await session.commit()
        return inserted

    async def _insert_values(
        self,
        session: AsyncSession,
        values: list[dict[str, Any]],
    ) -> int:
        dialect = session.get_bind().dialect.name
        inserted = 0
        for chunk in _chunks(values, _INSERT_CHUNK):
            if dialect == "postgresql":
                statement = (
                    postgres_insert(FactNetworkFlow)
                    .values(chunk)
                    .on_conflict_do_nothing(index_elements=["flow_id"])
                )
                result = await session.execute(statement)
                inserted += int(result.rowcount or 0)
            elif dialect == "sqlite":
                statement = (
                    sqlite_insert(FactNetworkFlow)
                    .values(chunk)
                    .on_conflict_do_nothing(index_elements=["flow_id"])
                )
                result = await session.execute(statement)
                inserted += int(result.rowcount or 0)
            else:
                session.add_all(FactNetworkFlow(**row) for row in chunk)
                await session.flush()
                inserted += len(chunk)
        return inserted

    async def _ensure_protocols(
        self, session: AsyncSession, flows: list[NetworkFlow]
    ) -> dict[str, int]:
        names = {flow.proto.value for flow in flows}
        missing = names - self._protocol_ids.keys()
        if missing:
            result = await session.execute(
                select(DimProtocol).where(DimProtocol.name.in_(missing))
            )
            for row in result.scalars():
                self._protocol_ids[row.name] = row.id
            new_rows = [
                DimProtocol(name=name)
                for name in missing
                if name not in self._protocol_ids
            ]
            if new_rows:
                session.add_all(new_rows)
                await session.flush()
                for row in new_rows:
                    self._protocol_ids[row.name] = row.id
        return {name: self._protocol_ids[name] for name in names}

    async def _ensure_conn_states(
        self, session: AsyncSession, flows: list[NetworkFlow]
    ) -> dict[str, int]:
        names = {flow.conn_state for flow in flows if flow.conn_state is not None}
        missing = names - self._conn_state_ids.keys()
        if missing:
            result = await session.execute(
                select(DimConnState).where(DimConnState.name.in_(missing))
            )
            for row in result.scalars():
                self._conn_state_ids[row.name] = row.id
            new_rows = [
                DimConnState(name=name)
                for name in missing
                if name not in self._conn_state_ids
            ]
            if new_rows:
                session.add_all(new_rows)
                await session.flush()
                for row in new_rows:
                    self._conn_state_ids[row.name] = row.id
        return {name: self._conn_state_ids[name] for name in names}

    async def _ensure_mitre_tactics(self, session: AsyncSession) -> dict[str, int]:
        if self._tactic_ids:
            return self._tactic_ids
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
        self._tactic_ids = ids
        return ids

    def _to_fact_values(
        self,
        flow: NetworkFlow,
        protocol_id: int,
        conn_state_id: int | None,
        tactic_ids: dict[str, int],
    ) -> dict[str, Any]:
        tactic_id = tactic_ids.get(flow.mitre_tactic) if flow.mitre_tactic else None
        return {
            "flow_id": str(flow.flow_id),
            "src_ip": flow.src_ip.value,
            "dst_ip": flow.dst_ip.value,
            "src_port": flow.src_port.value,
            "dst_port": flow.dst_port.value,
            "protocol_id": protocol_id,
            "conn_state_id": conn_state_id,
            "tactic_id": tactic_id,
            "ts": flow.ts.value,
            "orig_bytes": flow.orig_bytes,
            "resp_bytes": flow.resp_bytes,
            "duration": flow.duration,
            "iat_ms": flow.iat_ms,
            "anomaly_probability": flow.anomaly_probability,
            "is_anomaly": flow.anomaly_probability >= self._epsilon,
        }


def _chunks(
    values: Sequence[dict[str, Any]], size: int
) -> Sequence[Sequence[dict[str, Any]]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
