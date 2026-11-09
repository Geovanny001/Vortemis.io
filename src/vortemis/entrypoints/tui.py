import asyncio
from datetime import datetime

from rich.text import Text
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static

from vortemis.config import Settings
from vortemis.infrastructure.persistence.models import (
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
)


class KpiBox(Static):
    def __init__(self, label: str, accent: str, box_id: str) -> None:
        super().__init__(id=box_id)
        self._label = label
        self._accent = accent

    def render(self) -> str:
        value = "0"
        return f"[{self._accent} bold]{value}[/]\n[dim]{self._label}[/]"

    def set_value(self, value: str) -> None:
        self.update(f"[{self._accent} bold]{value}[/]\n[dim]{self._label}[/]")


class VortemisTUI(App):
    CSS = """
    KpiBox { border: heavy $primary; padding: 1 2; height: 3; }
    #status { background: $boost; padding: 0 2; }
    #left_panel { width: 32%; border: round $primary; padding: 0 1; }
    #flows_table { width: 68%; height: 20; }
    #inspector { height: 6; border: round $primary; padding: 0 1; }
    """

    BINDINGS = [
        Binding("a", "toggle_filter", "Only Anomalies"),
        Binding("plus,equals", "raise_epsilon", "+0.05"),
        Binding("minus", "lower_epsilon", "-0.05"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "Vortemis.io TUI — Passive Network Anomaly & MITRE ATT&CK Monitor"

    def __init__(self) -> None:
        super().__init__()
        self._settings = Settings.from_env()
        self._epsilon = self._settings.epsilon
        self._only_anomalies = False
        self._flows: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Initializing...", id="status")
        with Horizontal():
            yield KpiBox("Total Flows", "cyan", "kpi_total")
            yield KpiBox("Anomalies", "red", "kpi_anomalies")
            yield KpiBox("TA0010 Exfil", "yellow", "kpi_exfil")
            yield KpiBox("Recon & Lateral", "orange", "kpi_recon")
            yield KpiBox("C2 & Impact", "magenta", "kpi_c2")
        with Horizontal():
            yield Static("Top Risk Source Hosts", id="left_panel")
            yield DataTable(id="flows_table", cursor_type="row")
        yield Static("Select a row to inspect", id="inspector")
        yield Footer()

    async def on_mount(self) -> None:
        self._engine = create_async_engine(self._settings.database_url)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        table = self.query_one("#flows_table", DataTable)
        table.add_columns(
            "Timestamp", "Src IP", "Dst IP", "Dst Port", "Proto", "State",
            "IAT(ms)", "Orig Bytes", "P(Anomaly)", "MITRE",
        )
        self.set_interval(2.0, self.refresh_data)
        await self.refresh_data()

    async def refresh_data(self) -> None:
        async with self._session_factory() as session:
            total = await session.scalar(select(func.count()).select_from(FactNetworkFlow)) or 0
            anomalies = (
                await session.scalar(
                    select(func.count()).select_from(FactNetworkFlow).where(
                        FactNetworkFlow.anomaly_probability >= self._epsilon
                    )
                )
                or 0
            )
            rows = (
                await session.execute(
                    select(
                        FactNetworkFlow.ts,
                        FactNetworkFlow.src_ip,
                        FactNetworkFlow.dst_ip,
                        FactNetworkFlow.dst_port,
                        DimProtocol.name,
                        FactNetworkFlow.iat_ms,
                        FactNetworkFlow.orig_bytes,
                        FactNetworkFlow.anomaly_probability,
                        DimMitreTactic.mitre_id,
                    )
                    .join(DimProtocol, FactNetworkFlow.protocol_id == DimProtocol.id)
                    .outerjoin(
                        DimMitreTactic,
                        FactNetworkFlow.tactic_id == DimMitreTactic.tactic_id,
                    )
                    .order_by(FactNetworkFlow.ts.desc())
                    .limit(50)
                )
            ).all()

        self._flows = [
            {
                "ts": r[0].strftime("%H:%M:%S"),
                "src": r[1],
                "dst": r[2],
                "port": r[3],
                "proto": r[4],
                "iat": r[5],
                "bytes": r[6],
                "prob": r[7],
                "mitre": r[8] or "-",
            }
            for r in rows
        ]

        mitre_counts: dict[str, int] = {}
        for flow in self._flows:
            if flow["mitre"] != "-":
                mitre_counts[flow["mitre"]] = mitre_counts.get(flow["mitre"], 0) + 1

        exfil = mitre_counts.get("TA0010", 0)
        recon = mitre_counts.get("TA0043", 0) + mitre_counts.get("TA0008", 0)
        c2 = mitre_counts.get("TA0011", 0) + mitre_counts.get("TA0040", 0)

        self.query_one("#kpi_total", KpiBox).set_value(str(total))
        self.query_one("#kpi_anomalies", KpiBox).set_value(str(anomalies))
        self.query_one("#kpi_exfil", KpiBox).set_value(str(exfil))
        self.query_one("#kpi_recon", KpiBox).set_value(str(recon))
        self.query_one("#kpi_c2", KpiBox).set_value(str(c2))

        status = (
            f"model={self._settings.model_path}  epsilon={self._epsilon:.2f}  "
            f"filter={'ANOMALIES ONLY' if self._only_anomalies else 'ALL FLOWS'}  "
            f"db=connected  refresh=2.0s  {datetime.now().strftime('%H:%M:%S')}"
        )
        self.query_one("#status", Static).update(status)

        table = self.query_one("#flows_table", DataTable)
        table.clear()
        flows = self._flows if not self._only_anomalies else [
            f for f in self._flows if f["prob"] >= self._epsilon
        ]
        for flow in flows:
            table.add_row(
                flow["ts"], flow["src"], flow["dst"], str(flow["port"]),
                flow["proto"], "-", "—" if flow["iat"] is None else f"{flow['iat']:.1f}",
                str(flow["bytes"]), f"{flow['prob']:.3f}", flow["mitre"],
            )

        left = self.query_one("#left_panel", Static)
        risk = self._top_risk_sources()
        left.update(Text.from_markup(risk))

    def _top_risk_sources(self) -> str:
        sources: dict[str, list[float]] = {}
        for flow in self._flows:
            sources.setdefault(flow["src"], []).append(flow["prob"])
        ranked = sorted(
            ((ip, max(probs)) for ip, probs in sources.items()),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
        lines = ["[bold]Top Risk Source Hosts[/]\n"]
        for ip, prob in ranked:
            color = "red" if prob >= self._epsilon else "yellow" if prob >= 0.5 else "green"
            lines.append(f"[{color}]{ip}[/]  {prob:.3f}")
        return "\n".join(lines)

    def action_toggle_filter(self) -> None:
        self._only_anomalies = not self._only_anomalies

    def action_raise_epsilon(self) -> None:
        self._epsilon = min(0.99, round(self._epsilon + 0.05, 2))

    def action_lower_epsilon(self) -> None:
        self._epsilon = max(0.10, round(self._epsilon - 0.05, 2))

    def action_refresh(self) -> None:
        asyncio.create_task(self.refresh_data())

    def action_quit(self) -> None:
        self.exit()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        flows = self._flows if not self._only_anomalies else [
            f for f in self._flows if f["prob"] >= self._epsilon
        ]
        if event.row_key.value >= len(flows):
            return
        flow = flows[event.row_key.value]
        inspector = self.query_one("#inspector", Static)
        inspector.update(
            Text.from_markup(
                f"[bold]Inspector[/]  {flow['src']} → {flow['dst']}:{flow['port']}  "
                f"proto={flow['proto']}  iat={flow['iat']}ms  bytes={flow['bytes']}  "
                f"P(anomaly)={flow['prob']:.3f}  mitre={flow['mitre']}"
            )
        )


def main() -> None:
    VortemisTUI().run()


if __name__ == "__main__":
    main()
