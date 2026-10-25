import asyncio
import os

import pandas
import plotly.express as px
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimProtocol,
    FactNetworkFlow,
)

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
PAGE_TITLE = "VORTEMIS SOC - Threat Intelligence Dashboard"


async def load_dashboard_data(
    database_url: str,
) -> tuple[int, int, int, pandas.DataFrame, pandas.DataFrame]:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        total_flows = (
            await session.scalar(select(func.count()).select_from(FactNetworkFlow))
            or 0
        )
        total_protocols = (
            await session.scalar(select(func.count()).select_from(DimProtocol)) or 0
        )
        total_bytes = await session.scalar(
            select(
                func.coalesce(
                    func.sum(FactNetworkFlow.orig_bytes + FactNetworkFlow.resp_bytes), 0
                )
            )
        ) or 0
        protocol_rows = (
            await session.execute(
                select(DimProtocol.name, func.count(FactNetworkFlow.id))
                .join(FactNetworkFlow, FactNetworkFlow.protocol_id == DimProtocol.id)
                .group_by(DimProtocol.name)
                .order_by(func.count(FactNetworkFlow.id).desc())
            )
        ).all()
        latest_rows = (
            await session.execute(
                select(
                    FactNetworkFlow.ts,
                    FactNetworkFlow.src_ip,
                    FactNetworkFlow.src_port,
                    FactNetworkFlow.dst_ip,
                    FactNetworkFlow.dst_port,
                    DimProtocol.name,
                    FactNetworkFlow.duration,
                    FactNetworkFlow.orig_bytes,
                    FactNetworkFlow.resp_bytes,
                    DimConnState.name,
                )
                .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
                .outerjoin(
                    DimConnState, FactNetworkFlow.conn_state_id == DimConnState.id
                )
                .order_by(FactNetworkFlow.ts.desc())
                .limit(50)
            )
        ).all()
    await engine.dispose()

    protocol_frame = pandas.DataFrame(protocol_rows, columns=["protocol", "flows"])
    latest_frame = pandas.DataFrame(
        latest_rows,
        columns=[
            "ts",
            "src_ip",
            "src_port",
            "dst_ip",
            "dst_port",
            "protocol",
            "duration",
            "orig_bytes",
            "resp_bytes",
            "conn_state",
        ],
    )
    return total_flows, total_protocols, total_bytes, protocol_frame, latest_frame


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    st.title(PAGE_TITLE)
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)

    try:
        total_flows, total_protocols, total_bytes, protocol_frame, latest_frame = (
            asyncio.run(load_dashboard_data(database_url))
        )
    except Exception as exc:
        st.error(f"Unable to reach the database: {exc}")
        st.stop()

    column1, column2, column3 = st.columns(3)
    column1.metric("Total Flows", total_flows)
    column2.metric("Protocols Seen", total_protocols)
    column3.metric("Total Bytes", total_bytes)

    st.subheader("Top Protocols")
    st.plotly_chart(
        px.bar(protocol_frame, x="protocol", y="flows", title="Flows by Protocol")
    )

    st.subheader("Latest Analyzed Flows")
    st.dataframe(latest_frame)


main()
