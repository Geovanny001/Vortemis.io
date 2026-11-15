import asyncio
import os
import time
from dataclasses import asdict
from pathlib import Path

import numpy
import pandas
import plotly.express as px
import streamlit as st

from vortemis.application.mitre import MITRE_TACTICS
from vortemis.application.queries.telemetry import TelemetryReadService
from vortemis.application.use_cases.bayesian_pytorch_engine import (
    build_feature_vector,
    load_checkpoint,
)
from vortemis.application.validation import (
    validate_date_range,
    validate_ip_filter,
    validate_port_filter,
)
from vortemis.entrypoints.container import build_telemetry_service
from vortemis.infrastructure.persistence.login_limiter import LoginLimiter

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
LOG_FILE_ENV = "LOG_FILE"
DEFAULT_LOG_FILE = "conn.log"
MODEL_PATH_ENV = "MODEL_PATH"
DEFAULT_MODEL_PATH = "models/vortemis_ae.pt"
PAGE_TITLE = "Vortemis.io"

_LOGIN_LIMITER = LoginLimiter()

_FLOW_COLUMNS = [
    "ts",
    "flow_id",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "conn_state",
    "iat_ms",
    "orig_bytes",
    "resp_bytes",
    "duration",
    "anomaly_probability",
    "is_anomaly",
    "mitre_tactic",
]

_MITRE_COLORS = {
    "TA0010": "#ef4444",
    "TA0008": "#f97316",
    "TA0040": "#a855f7",
    "TA0043": "#f59e0b",
    "TA0011": "#06b6d4",
}

_MITRE_FORMULAS = {
    "TA0010": "SF & PCR > 0.60 & orig_bytes >= 25000",
    "TA0008": "private src & private dst & dst_port in {22,135,139,445,3389,5985}",
    "TA0040": "iat_ms < 2.0 & state in {S0,RSTO,RSTR,SH,OTH}",
    "TA0043": "state in {S0,REJ} & resp_bytes == 0 & duration < 0.05",
    "TA0011": "iat_ms < 50 & orig_bytes < 1500 | port in {53,80,443,8080,8443}",
}

_FEATURE_LABELS = [
    "log1p(iat_ms)",
    "log1p(orig_bytes)",
    "log1p(resp_bytes)",
    "log1p(duration)",
    "PCR",
    "is_failed_conn",
]

_CSS = """
<style>
.stApp { background-color: #0b0f19; }
[data-testid="stSidebar"] { background-color: #0d1117; }
.metric-card {
    background: linear-gradient(145deg, #111827 0%, #161f33 100%);
    border: 1px solid #1f2937;
    border-top: 3px solid #06b6d4;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
}
.metric-label { color: #8b949e; font-size: 13px; font-weight: 600; }
.metric-value {
    font-size: 26px;
    font-weight: 700;
    margin-top: 4px;
    font-family: 'JetBrains Mono', monospace;
}
.status-badge {
    display: inline-block;
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 6px;
    padding: 4px 10px;
    margin-right: 8px;
    font-family: monospace;
    font-size: 12px;
    color: #10b981;
}
.status-badge .dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: #10b981; margin-right: 6px;
    animation: pulse 1.5s infinite;
}
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
.login-card {
    background: linear-gradient(145deg, #111827 0%, #161f33 100%);
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 32px;
    max-width: 420px;
    margin: 80px auto;
}
.mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; }
</style>
"""


async def load_flows(service: TelemetryReadService) -> pandas.DataFrame:
    page = await service.search_flows(limit=20000)
    frame = pandas.DataFrame(
        [asdict(record) for record in page.records],
        columns=_FLOW_COLUMNS,
    )
    if not frame.empty:
        frame["ts"] = pandas.to_datetime(frame["ts"])
    return frame


async def authenticate(
    service: TelemetryReadService,
    username: str,
    password: str,
) -> str | None:
    identity = await service.authenticate(username, password)
    return identity.role if identity is not None else None


def load_model_metadata(model_path: Path) -> dict | None:
    if not model_path.exists():
        return None
    checkpoint = load_checkpoint(model_path)
    return {
        "tau": float(checkpoint["tau"]),
        "mu": numpy.asarray(checkpoint["mu"], dtype="float32"),
        "sigma": numpy.asarray(checkpoint["sigma"], dtype="float32"),
        "layers": "6 -> 16 -> 3 -> 16 -> 6",
    }


def _log_status(log_file: Path) -> tuple[str, str]:
    if not log_file.exists():
        return ("LOG MISSING", "#ef4444")
    age = max(0.0, time.time() - log_file.stat().st_mtime)
    if age <= 10.0:
        return ("RECEIVING LIVE", "#10b981")
    if age <= 300.0:
        return (f"IDLE {age:.0f}s", "#f59e0b")
    return ("IDLE", "#f59e0b")


def render_status_bar(
    username: str,
    role: str,
    tau: float | None,
    log_file: Path,
) -> None:
    tau_text = f"tau={tau:.4f}" if tau is not None else "tau=N/A"
    sensor_text, sensor_color = _log_status(log_file)
    st.markdown(
        f"""
        <div style="padding:8px 0 16px 0;">
          <div style="font-size:22px; font-weight:800; color:#e5e7eb;">
            VORTEMIS.IO // AUTONOMOUS PASSIVE NETWORK ANOMALY &amp; MITRE ATT&amp;CK ENGINE
          </div>
          <div style="margin-top:8px;">
            <span class="status-badge"><span class="dot" style="background:{sensor_color};"></span>
              SENSOR: {sensor_text}</span>
            <span class="status-badge"><span class="dot"></span>
              ENGINE: PYTORCH AUTOENCODER (R^6 -&gt; R^3 -&gt; R^6 | {tau_text})</span>
            <span class="status-badge"><span class="dot"></span>
              STORAGE: POSTGRESQL 16 STAR-SCHEMA</span>
            <span class="status-badge"><span class="dot"></span>
              OPERATOR: {username} [ROLE: {role.upper()}]</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, accent: str) -> None:
    st.markdown(
        f'<div class="metric-card" style="border-top-color:{accent};">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{accent};">{value}</div></div>',
        unsafe_allow_html=True,
    )


def render_kpis(frame: pandas.DataFrame, threshold: float) -> None:
    anomalies = frame[frame["anomaly_probability"] >= threshold]
    exfil = frame[frame["mitre_tactic"] == "TA0010"]
    recon_lateral = frame[frame["mitre_tactic"].isin(["TA0043", "TA0008"])]
    c2_impact = frame[frame["mitre_tactic"].isin(["TA0011", "TA0040"])]
    columns = st.columns(5)
    metrics = [
        ("Total Flows Analyzed", str(len(frame)), "#06b6d4"),
        ("Confirmed Anomalies", str(len(anomalies)), "#ef4444"),
        ("Exfiltration (TA0010)", str(len(exfil)), "#ef4444"),
        ("Recon & Lateral", str(len(recon_lateral)), "#f59e0b"),
        ("C2 & Impact", str(len(c2_impact)), "#a855f7"),
    ]
    for column, (label, value, accent) in zip(columns, metrics, strict=False):
        with column:
            render_metric_card(label, value, accent)


def apply_filters(frame: pandas.DataFrame, filters: dict) -> pandas.DataFrame:
    filtered = frame
    if filters["src_ip"]:
        filtered = filtered[filtered["src_ip"].str.contains(filters["src_ip"])]
    if filters["dst_port"]:
        filtered = filtered[filtered["dst_port"] == filters["dst_port"]]
    if filters["protocols"]:
        filtered = filtered[filtered["protocol"].str.upper().isin(filters["protocols"])]
    if filters["only_anomalies"]:
        filtered = filtered[filtered["anomaly_probability"] >= filters["threshold"]]
    if len(filters["date_range"]) == 2:
        start, end = filters["date_range"]
        filtered = filtered[(filtered["ts"].dt.date >= start) & (filtered["ts"].dt.date <= end)]
    return filtered


def render_sidebar(
    role: str,
    service: TelemetryReadService,
    log_file: Path,
) -> dict:
    with st.sidebar:
        st.subheader(f"Operator: {st.session_state.username}")
        st.write(f"Role: **{role.upper()}**")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.operator = None
            st.rerun()

        st.divider()
        st.subheader("Filters")
        date_range = st.date_input("Date Range", value=())
        src_ip = st.text_input("Source IP", placeholder="e.g., 192.168.1.50")
        dst_port = st.text_input("Destination Port", placeholder="e.g., 22 or 443")
        protocols = st.multiselect("Protocol", ["TCP", "UDP", "ICMP"])

        if role == "admin":
            threshold = st.slider("Probabilistic Threshold (epsilon)", 0.10, 0.99, 0.70, 0.01)
        else:
            threshold = st.slider(
                "Probabilistic Threshold (epsilon)", 0.10, 0.99, 0.70, 0.01, disabled=True
            )
            st.caption("Read-Only Policy: Threshold locked by SOC Administrator")

        only_anomalies = st.checkbox("Only Anomalies (P >= epsilon)")
        live_refresh = st.toggle("Live Refresh (2s)", value=False)

        ip_error = validate_ip_filter(src_ip)
        port_error = validate_port_filter(dst_port)
        date_error = validate_date_range(
            date_range[0] if len(date_range) == 2 else None,
            date_range[1] if len(date_range) == 2 else None,
        )
        for error in (ip_error, port_error, date_error):
            if error:
                st.error(error)

        if role == "admin":
            st.divider()
            with st.expander("Danger Zone"):
                st.caption("Delete all telemetry and reset the log to its header.")
                confirmed = st.checkbox("I understand this cannot be undone")
                if st.button(
                    "Purge All Telemetry Data",
                    disabled=not confirmed,
                    use_container_width=True,
                ):
                    with st.spinner("Purging telemetry..."):
                        try:
                            asyncio.run(service.purge(log_file))
                        except Exception as exc:
                            st.error(f"Purge failed: {exc}")
                        else:
                            st.success("Telemetry purged")
                            st.rerun()

        return {
            "src_ip": src_ip if not ip_error else "",
            "dst_port": int(dst_port) if dst_port and not port_error else 0,
            "protocols": protocols,
            "threshold": threshold,
            "only_anomalies": only_anomalies,
            "date_range": date_range,
            "live_refresh": live_refresh,
        }


def render_tab_overview(frame: pandas.DataFrame, threshold: float) -> None:
    anomalies = frame[frame["anomaly_probability"] >= threshold]

    left, right = st.columns(2)
    with left:
        st.subheader("MITRE ATT&CK Network Tactics Breakdown")
        if frame["mitre_tactic"].notna().any():
            counts = (
                frame[frame["mitre_tactic"].notna()]
                .groupby("mitre_tactic")
                .size()
                .reset_index(name="count")
            )
            bar = px.bar(counts, x="count", y="mitre_tactic", orientation="h")
            bar.update_traces(
                marker_color=[_MITRE_COLORS.get(t, "#06b6d4") for t in counts["mitre_tactic"]]
            )
            bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("No MITRE tactic data yet")

    with right:
        st.subheader("Posterior Probability Distribution P(Anomaly | x)")
        histogram = px.histogram(frame, x="anomaly_probability", nbins=40)
        histogram.add_vline(
            x=threshold,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text="epsilon",
        )
        histogram.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(histogram, use_container_width=True)

    st.subheader("Real-Time Network Anomaly Timeline")
    if not anomalies.empty:
        trend_frame = anomalies.copy()
        trend_frame["minute"] = trend_frame["ts"].dt.floor("min")
        trend = trend_frame.groupby("minute").size().reset_index(name="anomaly_count")
        line = px.line(trend, x="minute", y="anomaly_count")
        line.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(line, use_container_width=True)
    else:
        st.info("No anomalies to trend")

    st.subheader("Top Offending Source IPs")
    risk = (
        frame.groupby("src_ip")
        .agg(max_prob=("anomaly_probability", "max"), flows=("anomaly_probability", "size"))
        .sort_values("max_prob", ascending=False)
        .head(10)
        .reset_index()
    )
    st.dataframe(risk, hide_index=True)


def render_tab_forensic(frame: pandas.DataFrame, metadata: dict | None) -> None:
    st.subheader("Deep Flow Forensic Inspector")
    st.dataframe(
        frame[
            [
                "ts", "flow_id", "src_ip", "dst_ip", "src_port", "dst_port",
                "protocol", "conn_state", "iat_ms", "orig_bytes", "resp_bytes",
                "anomaly_probability", "mitre_tactic",
            ]
        ],
        use_container_width=True,
    )
    if frame.empty:
        st.info("No network flows match the current filter criteria")
        return

    st.subheader("Individual Flow Inspector (Deep-Dive)")
    choices: list[tuple[str, str]] = []
    for _, row in frame.iterrows():
        risk = float(row["anomaly_probability"]) * 100.0
        tactic = (
            "NO-TACTIC"
            if pandas.isna(row["mitre_tactic"])
            else str(row["mitre_tactic"])
        )
        protocol = str(row["protocol"]).upper()
        label = (
            f"[Risk: {risk:.1f}% | {tactic}] "
            f"{row['src_ip']} -> {row['dst_ip']}:{row['dst_port']} ({protocol})"
        )
        choices.append((f"{label} | {str(row['flow_id'])[:8]}", str(row["flow_id"])))
    selected_label = st.selectbox("Select flow", [choice[0] for choice in choices])
    selected_id = next(flow_id for label, flow_id in choices if label == selected_label)
    row = frame[frame["flow_id"] == selected_id].iloc[0]

    iat_ms = None if pandas.isna(row["iat_ms"]) else float(row["iat_ms"])
    conn_state = None if pandas.isna(row["conn_state"]) else str(row["conn_state"])
    features = build_feature_vector(
        iat_ms=iat_ms,
        orig_bytes=int(row["orig_bytes"]),
        resp_bytes=int(row["resp_bytes"]),
        duration=float(row["duration"]),
        conn_state=conn_state,
    )
    feature_frame = pandas.DataFrame(
        {"Feature": _FEATURE_LABELS, "Current Value": features}
    )
    if metadata is not None:
        z = (features - metadata["mu"]) / (metadata["sigma"] + 1e-8)
        feature_frame["Z-Score"] = z
        feature_frame["Status"] = [
            (
                "Normal"
                if abs(value) < 2.0
                else "Elevated"
                if abs(value) < 3.0
                else "Critical Deviation"
            )
            for value in z
        ]
    st.dataframe(feature_frame, hide_index=True, use_container_width=True)

    tactic = row["mitre_tactic"]
    if isinstance(tactic, str) and tactic in _MITRE_FORMULAS:
        st.info(f"MITRE {tactic} triggered: {_MITRE_FORMULAS[tactic]}")


def render_tab_mitre_matrix(frame: pandas.DataFrame) -> None:
    st.subheader("MITRE ATT&CK Network Matrix")
    tactic_frame = frame[frame["mitre_tactic"].notna()]
    total_alerts = len(tactic_frame)
    columns = st.columns(2)
    for index, (mitre_id, name) in enumerate(MITRE_TACTICS.items()):
        count = int((tactic_frame["mitre_tactic"] == mitre_id).sum())
        pct = (count / total_alerts * 100) if total_alerts else 0.0
        formula = _MITRE_FORMULAS.get(mitre_id, "")
        color = _MITRE_COLORS.get(mitre_id, "#06b6d4")
        top_ips = (
            frame[frame["mitre_tactic"] == mitre_id]["src_ip"].value_counts().head(3).index.tolist()
        )
        with columns[index % 2]:
            st.markdown(
                f"""
                <div class="metric-card" style="border-top-color:{color};">
                  <div style="font-size:16px; font-weight:700; color:{color};">
                    {mitre_id} — {name}
                  </div>
                  <div class="mono" style="color:#9ca3af; font-size:12px;">{formula}</div>
                  <div style="color:#e5e7eb; margin-top:6px;">
                    Events: {count} ({pct:.1f}% of alerts)
                  </div>
                  <div class="mono" style="color:#9ca3af; font-size:12px;">
                    Top sources: {', '.join(top_ips) if top_ips else 'none'}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_tab_diagnostics(metadata: dict | None, log_file: Path) -> None:
    st.subheader("PyTorch Engine & Sensor Diagnostics")
    if metadata is None:
        st.warning("models/vortemis_ae.pt not found")
    else:
        st.write(f"Architecture: `{metadata['layers']}`")
        st.write(f"tau (95th percentile): `{metadata['tau']:.4f}`")
        mu_frame = pandas.DataFrame({"feature": _FEATURE_LABELS, "mu": metadata["mu"]})
        st.dataframe(mu_frame, hide_index=True)
        sigma_frame = pandas.DataFrame({"feature": _FEATURE_LABELS, "sigma": metadata["sigma"]})
        st.dataframe(sigma_frame, hide_index=True)

    st.subheader("Sensor Log File Status")
    sensor_text, _ = _log_status(log_file)
    st.write(f"Status: **{sensor_text}**")
    if log_file.exists():
        size_kb = log_file.stat().st_size / 1024
        st.write(f"`{log_file}` — {size_kb:.2f} KB")
    else:
        st.warning(f"`{log_file}` not found")


def render_empty_state(log_file: Path) -> None:
    st.markdown(
        f"""
        <div class="metric-card" style="border-top-color:#06b6d4; padding:28px;">
          <div style="font-size:20px; font-weight:800; color:#e5e7eb;">
            No telemetry yet
          </div>
          <div style="color:#9ca3af; margin-top:8px;">
            The database is connected, but there are no network flows to analyze.
          </div>
          <div class="mono" style="color:#06b6d4; margin-top:14px;">
            uv run python -m vortemis.infrastructure.zeek.live_sensor<br>
            --interface wlan0 --log-file {log_file}
          </div>
          <div style="color:#9ca3af; margin-top:10px;">
            Start the sensor or append a Zeek conn.log. The dashboard will refresh automatically.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Waiting for telemetry...")


def render_login(service: TelemetryReadService) -> None:
    st.markdown(
        """
        <div class="login-card">
          <div style="text-align:center; font-size:26px; font-weight:800; color:#e5e7eb;">
            Vortemis.io
          </div>
          <div style="text-align:center; color:#9ca3af; margin-bottom:20px;">
            Zero-Trust Telemetry &amp; Stochastic Threat Hunting Console
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Authenticate", use_container_width=True):
                if not username or not password:
                    st.error("Username and password are required")
                elif _LOGIN_LIMITER.is_locked(username):
                    remaining = _LOGIN_LIMITER.remaining_seconds(username)
                    st.error(
                        f"Too many failed attempts. Try again in {remaining:.0f}s."
                    )
                else:
                    with st.spinner("Authenticating..."):
                        role = asyncio.run(
                            authenticate(service, username, password)
                        )
                    if role is None:
                        _LOGIN_LIMITER.record_failure(username)
                        remaining = _LOGIN_LIMITER.remaining_seconds(username)
                        if remaining > 0:
                            st.error(
                                "Invalid credentials. "
                                f"Account locked for {remaining:.0f}s."
                            )
                        else:
                            st.error("Invalid credentials")
                    else:
                        _LOGIN_LIMITER.record_success(username)
                        st.session_state.operator = username
                        st.session_state.role = role
                        st.session_state.username = username
                        st.rerun()


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)
    model_path = Path(os.getenv(MODEL_PATH_ENV, DEFAULT_MODEL_PATH))
    log_file = Path(os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE))
    service = build_telemetry_service(database_url)

    if not st.session_state.get("operator"):
        render_login(service)
        st.stop()

    username = st.session_state.operator
    role = st.session_state.role

    try:
        frame = asyncio.run(load_flows(service))
    except Exception as exc:
        st.error(f"Unable to reach the database: {exc}")
        st.stop()

    metadata = load_model_metadata(model_path)
    render_status_bar(
        username,
        role,
        metadata["tau"] if metadata else None,
        log_file,
    )

    filters = render_sidebar(role, service, log_file)
    if frame.empty:
        render_empty_state(log_file)
        st.stop()

    filtered = apply_filters(frame, filters)
    render_kpis(filtered, filters["threshold"])

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Live SOC Overview & Threat Telemetry",
            "Deep Flow Forensic Inspector",
            "MITRE ATT&CK Network Matrix",
            "PyTorch Engine & Sensor Diagnostics",
        ]
    )

    with tab1:
        render_tab_overview(filtered, filters["threshold"])
    with tab2:
        render_tab_forensic(filtered, metadata)
    with tab3:
        render_tab_mitre_matrix(filtered)
    with tab4:
        render_tab_diagnostics(metadata, log_file)

    st.download_button(
        "Export Forensic Report (CSV)",
        data=filtered.to_csv(index=False),
        file_name="forensic_report.csv",
        mime="text/csv",
    )

    if filters["live_refresh"]:
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
