from pathlib import Path

from vortemis.application.ports.driving.telemetry_source import TelemetrySourcePort
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource


async def test_stream_reads_tsv_and_ignores_zeek_headers(tmp_path: Path) -> None:
    lines = [
        "#separator \\x09",
        "#set_separator\t,",
        "#empty_field\t(empty)",
        "#unset_field\t-",
        "#path\tconn",
        "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto",
        "#types\ttime\tstring\taddr\tport\taddr\tport\tenum",
        "1.5\tC1\t192.168.1.1\t12345\t10.0.0.2\t80\ttcp",
        "2.5\tC2\t192.168.1.1\t12346\t10.0.0.2\t443\tudp",
    ]
    path = tmp_path / "conn.log"
    path.write_text("\n".join(lines) + "\n")

    records = [record async for record in ZeekTelemetrySource(path).stream()]

    assert len(records) == 2
    assert records[0].source_line == 8
    assert records[0].data == {
        "ts": "1.5",
        "uid": "C1",
        "id.orig_h": "192.168.1.1",
        "id.orig_p": "12345",
        "id.resp_h": "10.0.0.2",
        "id.resp_p": "80",
        "proto": "tcp",
    }
    assert records[1].data["uid"] == "C2"
    assert records[1].data["proto"] == "udp"


async def test_stream_reads_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "conn.json"
    path.write_text(
        '{"ts": 1.5, "uid": "C1", "proto": "tcp"}\n'
        '{"ts": 2.5, "uid": "C2", "proto": "udp"}\n'
    )

    records = [record async for record in ZeekTelemetrySource(path).stream()]

    assert len(records) == 2
    assert records[0].data == {"ts": "1.5", "uid": "C1", "proto": "tcp"}
    assert records[1].data == {"ts": "2.5", "uid": "C2", "proto": "udp"}


async def test_zeek_telemetry_source_satisfies_telemetry_source_port(
    tmp_path: Path,
) -> None:
    path = tmp_path / "conn.log"
    path.write_text("#fields\tid.orig_h\tid.resp_h\n1.1.1.1\t2.2.2.2\n")

    source: TelemetrySourcePort = ZeekTelemetrySource(path)
    records = [record async for record in source.stream()]

    assert len(records) == 1
    assert records[0].data == {"id.orig_h": "1.1.1.1", "id.resp_h": "2.2.2.2"}
