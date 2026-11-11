from textual.widgets import DataTable, Static

from vortemis.banner import CREDITS, SUBTITLE
from vortemis.entrypoints.tui import KpiBox, VortemisTUI


def test_banner_branding() -> None:
    assert "Vortemis.io" in SUBTITLE
    assert "Vortemis.io" in CREDITS


async def test_tui_smoke_renders_kpis_and_shortcuts(monkeypatch) -> None:
    async def _noop(self: VortemisTUI) -> None:
        return None

    monkeypatch.setattr(VortemisTUI, "refresh_data", _noop)
    app = VortemisTUI()

    async with app.run_test() as pilot:
        assert len(app.query(KpiBox)) == 5
        assert app.query_one("#flows_table", DataTable) is not None
        assert app.query_one("#status", Static) is not None

        app._epsilon = 0.50
        await pilot.press("plus")
        assert app._epsilon == 0.55
        await pilot.press("minus")
        assert app._epsilon == 0.50

        await pilot.press("a")
        assert app._only_anomalies is True
        await pilot.press("a")
        assert app._only_anomalies is False
