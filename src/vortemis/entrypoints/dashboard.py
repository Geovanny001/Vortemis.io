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
)
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
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
    "anomaly_probability",
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
                    FactNetworkFlow.anomaly_probability,
                    FactNetworkFlow.is_anomaly,
                    DimMitreTactic.mitre_id,
                )
                .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
                .outerjoin(
                    DimConnState, FactNetworkFlow.conn_state_id == DimConnState.id
                )
                .outerjoin(
                    DimMitreTactic,
                    FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
                )
                .order_by(FactNetworkFlow.ts.desc())
            )
        ).all()
    await engine.dispose()
    frame = pandas.DataFrame(rows, columns=_FLOW_COLUMNS)
    frame["ts"] = pandas.to_datetime(frame["ts"])
    return frame


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
    if filters["mitre_tactics"]:
        filtered = filtered[filtered["mitre_tactic"].isin(filters["mitre_tactics"])]
    if filters["only_anomalies"]:
        filtered = filtered[filtered["anomaly_probability"] >= filters["threshold"]]
    if len(filters["date_range"]) == 2:
        start, end = filters["date_range"]
        filtered = filtered[
            (filtered["ts"].dt.date >= start) & (filtered["ts"].dt.date <= end)
        ]
    return filtered


def render_overview(frame: pandas.DataFrame, threshold: float) -> None:
    anomalies = frame[frame["anomaly_probability"] >= threshold]
    exfiltration = frame[frame["mitre_tactic"] == "TA0010"]
    recon_lateral = frame[frame["mitre_tactic"].isin(["TA0043", "TA0008"])]
    c2_impact = frame[frame["mitre_tactic"].isin(["TA0011", "TA0040"])]

    columns = st.columns(5)
    metrics = [
        ("Total Flows Analyzed", str(len(frame)), "#c9d1d9"),
        ("Detected Anomalies", str(len(anomalies)), "#f85149"),
        ("Data Exfiltration", str(len(exfiltration)), "#d29922"),
        ("Recon & Lateral", str(len(recon_lateral)), "#58a6ff"),
        ("C2 & Impact Flood", str(len(c2_impact)), "#bc8cff"),
    ]
    for column, (label, value, color) in zip(columns, metrics, strict=False):
        with column:
            render_metric_card(label, value, color)

    left, middle, right = st.columns([1, 2, 2])

    with left:
        st.subheader("Top Risk Source IPs")
        risk = (
            frame.groupby("src_ip")["anomaly_probability"]
            .max()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .rename(columns={"anomaly_probability": "max_risk"})
        )
        st.dataframe(risk, hide_index=True)

    with middle:
        st.subheader("Posterior Probability Distribution")
        histogram = px.histogram(
            frame,
            x="anomaly_probability",
            nbins=40,
            title="P(Anomaly | Metadata)",
        )
        histogram.add_vline(
            x=threshold, line_dash="dash", line_color="red", annotation_text="epsilon"
        )
        histogram.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(histogram, use_container_width=True)

    with right:
        st.subheader("MITRE Tactic Breakdown")
        if frame["mitre_tactic"].notna().any():
            mitre_counts = (
                frame[frame["mitre_tactic"].notna()]
                .groupby("mitre_tactic")
                .size()
                .reset_index(name="count")
            )
            bar = px.bar(mitre_counts, x="mitre_tactic", y="count")
            bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("No MITRE tactic data yet")

    st.subheader("Anomaly Trend Over Time")
    if not anomalies.empty:
        trend_frame = anomalies.copy()
        trend_frame["minute"] = trend_frame["ts"].dt.floor("min")
        trend = (
            trend_frame.groupby("minute")
            .size()
            .reset_index(name="anomaly_count")
        )
        line = px.line(trend, x="minute", y="anomaly_count")
        line.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(line, use_container_width=True)
    else:
        st.info("No anomalies to trend")

    st.subheader("Latest Analyzed Network Flows")
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
                "resp_bytes",
                "anomaly_probability",
                "mitre_tactic",
            ]
        ],
        use_container_width=True,
    )


def render_mitre_reports(frame: pandas.DataFrame) -> None:
    st.subheader("High Risk Anomalies")
    anomalies = frame[frame["mitre_tactic"].notna()].sort_values(
        "anomaly_probability", ascending=False
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
                "resp_bytes",
                "anomaly_probability",
                "mitre_tactic",
            ]
        ],
        use_container_width=True,
    )


def render_live_stream(frame: pandas.DataFrame, database_url: str) -> None:
    st.subheader("Database Status")
    st.write(f"Endpoint: `{database_url}`")
    st.success("Database connection active")

    st.subheader("Live Alert Stream")
    alerts = frame[frame["mitre_tactic"].notna()].sort_values("ts", ascending=False).head(20)
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
                    "anomaly_probability",
                    "mitre_tactic",
                ]
            ],
            use_container_width=True,
        )


def render_sidebar() -> dict:
    with st.sidebar:
        st.subheader("Controls & Analyst Use Cases")
        date_range = st.date_input("Date Range", value=())
        src_ip = st.text_input("Source IP")
        dst_port = st.number_input(
            "Destination Port", min_value=0, max_value=65535, value=0
        )
        protocols = st.multiselect("Protocol", ["TCP", "UDP", "ICMP"])
        mitre_tactics = st.multiselect(
            "MITRE Tactic", ["TA0010", "TA0008", "TA0040", "TA0043", "TA0011"]
        )
        threshold = st.slider(
            "Probabilistic Threshold (epsilon)", 0.10, 0.99, 0.70, 0.01
        )
        only_anomalies = st.checkbox("Only Anomalies (P > epsilon)")

        st.divider()
        if st.button("Apply Filters", use_container_width=True):
            st.toast("Filters applied")
        if st.button("Ingest New Zeek Batch", use_container_width=True):
            log_file = os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE)
            with st.spinner("Ingesting new Zeek batch..."):
                new_flows = asyncio.run(
                    run_ingestion(os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL), log_file)
                )
            st.toast(f"Ingestion complete: {new_flows} new flows processed")

        return {
            "src_ip": src_ip,
            "dst_port": dst_port,
            "protocols": protocols,
            "mitre_tactics": mitre_tactics,
            "threshold": threshold,
            "only_anomalies": only_anomalies,
            "date_range": date_range,
        }


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title(PAGE_TITLE)
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)

    filters = render_sidebar()

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
            "Live Alert Stream",
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
