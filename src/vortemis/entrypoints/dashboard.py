import asyncio
import os
from pathlib import Path

import pandas
import plotly.express as px
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.infrastructure.persistence.models import (
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
    SocUser,
)
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
from vortemis.infrastructure.security import verify_password
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
LOG_FILE_ENV = "LOG_FILE"
DEFAULT_LOG_FILE = "conn.log"
PAGE_TITLE = "VORTEMIS SOC - Threat Intelligence Dashboard"

_FLOW_COLUMNS = [
    "ts",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "conn_state",
    "iat_ms",
    "orig_bytes",
    "resp_bytes",
    "anomaly_score",
    "is_anomaly",
    "mitre_tactic",
]

_CSS = """
<style>
[data-testid="stSidebar"] {
    background-color: #0d1117;
}
.metric-card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
}
.metric-label {
    color: #8b949e;
    font-size: 13px;
    font-weight: 600;
}
.metric-value {
    font-size: 28px;
    font-weight: 700;
    margin-top: 4px;
}
</style>
"""


async def load_flows(database_url: str) -> pandas.DataFrame:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    FactNetworkFlow.ts,
                    FactNetworkFlow.src_ip,
                    FactNetworkFlow.dst_ip,
                    FactNetworkFlow.src_port,
                    FactNetworkFlow.dst_port,
                    DimProtocol.name,
                    DimConnState.name,
                    FactNetworkFlow.iat_ms,
                    FactNetworkFlow.orig_bytes,
                    FactNetworkFlow.resp_bytes,
                    FactNetworkFlow.anomaly_score,
                    FactNetworkFlow.is_anomaly,
                    DimMitreTactic.mitre_id,
                )
                .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
                .outerjoin(
                    DimConnState, FactNetworkFlow.conn_state_id == DimConnState.id
                )
                .outerjoin(
                    DimMitreTactic, FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id
                )
                .order_by(FactNetworkFlow.ts.desc())
            )
        ).all()
    await engine.dispose()
    frame = pandas.DataFrame(rows, columns=_FLOW_COLUMNS)
    frame["ts"] = pandas.to_datetime(frame["ts"])
    return frame


async def authenticate(database_url: str, username: str, password: str) -> str | None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await session.scalar(
            select(SocUser).where(SocUser.username == username)
        )
    await engine.dispose()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user.role


async def run_ingestion(database_url: str, log_file: str) -> int:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        before = (
            await session.scalar(select(func.count()).select_from(FactNetworkFlow)) or 0
        )
    use_case = FlowNormalizerUseCase(
        source=ZeekTelemetrySource(Path(log_file)),
        repository=PostgresFlowRepository(session_factory),
    )
    await use_case.execute()
    async with session_factory() as session:
        after = (
            await session.scalar(select(func.count()).select_from(FactNetworkFlow)) or 0
        )
    await engine.dispose()
    return after - before


def render_metric_card(label: str, value: str, color: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{color}">{value}</div></div>',
        unsafe_allow_html=True,
    )


def format_bytes(value: float) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.2f} MB"
    if value >= 1024:
        return f"{value / 1024:.2f} KB"
    return f"{value:.0f} B"


def apply_filters(frame: pandas.DataFrame, filters: dict) -> pandas.DataFrame:
    filtered = frame
    if filters["src_ip"]:
        filtered = filtered[filtered["src_ip"].str.contains(filters["src_ip"])]
    if filters["dst_port"]:
        filtered = filtered[filtered["dst_port"] == filters["dst_port"]]
    if filters["protocols"]:
        filtered = filtered[
            filtered["protocol"].str.upper().isin(filters["protocols"])
        ]
    if filters["only_anomalies"]:
        filtered = filtered[filtered["is_anomaly"]]
    if len(filters["date_range"]) == 2:
        start, end = filters["date_range"]
        filtered = filtered[
            (filtered["ts"].dt.date >= start) & (filtered["ts"].dt.date <= end)
        ]
    return filtered


def render_overview(frame: pandas.DataFrame, threshold: float) -> pandas.DataFrame:
    anomalies = frame[frame["anomaly_score"] >= threshold]
    exfiltration = frame[frame["orig_bytes"] > 4000]
    bursts = frame[frame["iat_ms"].notna() & (frame["iat_ms"] < 5.0)]

    columns = st.columns(5)
    metrics = [
        ("Overall Anomalies", str(len(anomalies)), "#f85149"),
        ("Exfiltration Alerts", str(len(exfiltration)), "#d29922"),
        ("Rapid Burst / C2 Threats", str(len(bursts)), "#58a6ff"),
        ("Total Analyzed Flows", str(len(frame)), "#3fb950"),
        (
            "Total Volume (Bytes)",
            format_bytes(
                float(frame["orig_bytes"].sum() + frame["resp_bytes"].sum())
            ),
            "#c9d1d9",
        ),
    ]
    for column, (label, value, color) in zip(columns, metrics, strict=False):
        with column:
            render_metric_card(label, value, color)

    left, middle, right = st.columns([1, 2, 2])

    with left:
        st.subheader("Top Risk Source IPs")
        risk = (
            frame.groupby("src_ip")["anomaly_score"]
            .max()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .rename(columns={"anomaly_score": "max_risk_score"})
        )
        st.dataframe(risk, hide_index=True)

    with middle:
        st.subheader("Anomaly Score Distribution")
        histogram = px.histogram(
            frame,
            x="anomaly_score",
            nbins=40,
            title="Anomaly Score Distribution",
        )
        histogram.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(histogram, use_container_width=True)

    with right:
        st.subheader("Traffic by Protocol & MITRE Tactics")
        protocol_counts = frame.groupby("protocol").size().reset_index(name="count")
        bar = px.bar(
            protocol_counts,
            x="protocol",
            y="count",
            title="Traffic by Protocol",
        )
        bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(bar, use_container_width=True)

    st.subheader("Anomaly Trends")
    if not anomalies.empty:
        anomalies = anomalies.copy()
        anomalies["minute"] = anomalies["ts"].dt.floor("min")
        trend = (
            anomalies.groupby("minute")
            .size()
            .reset_index(name="anomaly_count")
        )
        line = px.line(trend, x="minute", y="anomaly_count", title="Anomalies per Minute")
        line.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(line, use_container_width=True)
    else:
        st.info("No anomalies to trend")

    st.subheader("Forensic Flows")
    st.dataframe(
        frame[
            [
                "ts",
                "src_ip",
                "dst_ip",
                "src_port",
                "dst_port",
                "protocol",
                "conn_state",
                "iat_ms",
                "orig_bytes",
                "anomaly_score",
                "mitre_tactic",
            ]
        ],
        use_container_width=True,
    )
    return frame


def render_mitre_reports(frame: pandas.DataFrame) -> None:
    st.subheader("MITRE Tactic Breakdown")
    if frame["mitre_tactic"].notna().any():
        mitre_counts = (
            frame[frame["mitre_tactic"].notna()]
            .groupby("mitre_tactic")
            .size()
            .reset_index(name="count")
        )
        bar = px.bar(mitre_counts, x="mitre_tactic", y="count", title="Anomalies by MITRE Tactic")
        bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(bar, use_container_width=True)
    else:
        st.info("No MITRE tactic data yet")

    st.subheader("High Risk Anomalies")
    anomalies = frame[frame["is_anomaly"]].sort_values(
        "anomaly_score", ascending=False
    )
    st.dataframe(
        anomalies[
            [
                "ts",
                "src_ip",
                "dst_ip",
                "src_port",
                "dst_port",
                "protocol",
                "orig_bytes",
                "anomaly_score",
                "mitre_tactic",
            ]
        ],
        use_container_width=True,
    )


def render_live_stream(frame: pandas.DataFrame, database_url: str) -> None:
    st.subheader("API & Database Status")
    st.write(f"Database endpoint: `{database_url}`")
    st.success("Database connection active")

    st.subheader("Live Alert Stream")
    alerts = frame[frame["is_anomaly"]].sort_values("ts", ascending=False).head(20)
    if alerts.empty:
        st.info("No active alerts")
    else:
        st.dataframe(
            alerts[
                [
                    "ts",
                    "src_ip",
                    "dst_ip",
                    "src_port",
                    "dst_port",
                    "protocol",
                    "anomaly_score",
                    "mitre_tactic",
                ]
            ],
            use_container_width=True,
        )


def render_sidebar(database_url: str) -> dict | None:
    with st.sidebar:
        st.subheader("Authentication")
        if not st.session_state.get("logged_in", False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Sign In"):
                with st.spinner("Authenticating..."):
                    role = asyncio.run(authenticate(database_url, username, password))
                if role is None:
                    st.error("Invalid credentials")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.rerun()
            return None

        st.write(f"User: **{st.session_state.username}**")
        st.write(f"Role: **{st.session_state.role}**")
        if st.button("Sign Out"):
            st.session_state.logged_in = False
            st.rerun()

        st.divider()
        st.subheader("Filters")
        date_range = st.date_input("Date Range", value=())
        src_ip = st.text_input("Source IP")
        dst_port = st.number_input(
            "Destination Port", min_value=0, max_value=65535, value=0
        )
        protocols = st.multiselect("Protocol", ["TCP", "UDP", "ICMP"])
        only_anomalies = st.checkbox("Only Anomalies")
        threshold = st.slider(
            "Probabilistic Threshold P(Anomaly)", 0.10, 0.99, 0.50, 0.01
        )

        st.divider()
        st.subheader("Actions")
        apply_clicked = st.button("Apply Filters", use_container_width=True)
        if apply_clicked:
            st.toast("Filters applied")
        ingest_clicked = st.button(
            "Ingest New Zeek Batch", use_container_width=True
        )
        if ingest_clicked:
            log_file = os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE)
            with st.spinner("Ingesting new Zeek batch..."):
                new_flows = asyncio.run(run_ingestion(database_url, log_file))
            st.toast(f"Ingestion complete: {new_flows} new flows processed")

        return {
            "src_ip": src_ip,
            "dst_port": dst_port,
            "protocols": protocols,
            "only_anomalies": only_anomalies,
            "date_range": date_range,
            "threshold": threshold,
        }


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title(PAGE_TITLE)
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)

    filters = render_sidebar(database_url)
    if filters is None:
        st.info("Sign in to access the SOC dashboard")
        st.stop()

    try:
        frame = asyncio.run(load_flows(database_url))
    except Exception as exc:
        st.error(f"Unable to reach the database: {exc}")
        st.stop()

    filtered = apply_filters(frame, filters)

    overview, reports, live = st.tabs(
        [
            "Overview Dashboard",
            "Anomaly & MITRE Reports",
            "Live Alert Stream & API Status",
        ]
    )

    with overview:
        render_overview(filtered, filters["threshold"])

    with reports:
        render_mitre_reports(filtered)

    with live:
        render_live_stream(filtered, database_url)

    st.download_button(
        "Export Forensic Report (CSV)",
        data=filtered.to_csv(index=False),
        file_name="forensic_report.csv",
        mime="text/csv",
    )


main()
