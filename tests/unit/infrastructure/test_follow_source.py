import asyncio
from pathlib import Path

from vortemis.infrastructure.zeek import telemetry_source
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource

_HEADER = "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\n"
_ROW_1 = "1.0\tC1\t10.0.0.1\t1\t10.0.0.2\t80\ttcp\n"
_ROW_2 = "2.0\tC2\t10.0.0.1\t2\t10.0.0.2\t443\tudp\n"


async def test_follow_streams_appended_lines(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(telemetry_source, "_POLL_INTERVAL", 0.01)
    path = tmp_path / "conn.log"
    path.write_text(_HEADER + _ROW_1)
    source = ZeekTelemetrySource(path, follow=True)
    stream = source.stream()

    first = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert first.data["uid"] == "C1"

    with path.open("a") as handle:
        handle.write(_ROW_2)

    second = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert second.data["uid"] == "C2"
    await stream.aclose()


async def test_follow_waits_for_partial_line(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(telemetry_source, "_POLL_INTERVAL", 0.01)
    path = tmp_path / "conn.log"
    path.write_text(_HEADER + _ROW_1 + _ROW_2.rstrip("\n"))
    source = ZeekTelemetrySource(path, follow=True)
    stream = source.stream()

    first = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert first.data["uid"] == "C1"

    with path.open("a") as handle:
        handle.write("\n")

    second = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert second.data["uid"] == "C2"
    await stream.aclose()
