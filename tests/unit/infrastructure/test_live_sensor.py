import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from vortemis.infrastructure.zeek.live_sensor import (
    LiveTsharkSensor,
    aggregate_flows,
    parse_tshark_line,
)


def _tshark_line(
    ts: float | str,
    src: str,
    sport: int,
    dst: str,
    dport: int,
    proto: int,
    length: int,
    ack: str = "0",
) -> str:
    return "\t".join(
        [
            str(ts),
            src,
            str(sport),
            "",
            dst,
            str(dport),
            "",
            str(proto),
            str(length),
            "0",
            ack,
            "0",
            "0",
        ]
    )


def test_parse_and_aggregate_tshark_packets() -> None:
    packets = [
        parse_tshark_line(_tshark_line(1.0, "10.0.0.1", 1111, "10.0.0.2", 80, 6, 100)),
        parse_tshark_line(
            _tshark_line(2.0, "10.0.0.1", 1111, "10.0.0.2", 80, 6, 50, ack="1")
        ),
    ]
    assert all(packet is not None for packet in packets)
    flows = aggregate_flows(packets)
    assert len(flows) == 1
    fields = flows[0].split("\t")
    assert fields[2] == "10.0.0.1"
    assert fields[4] == "10.0.0.2"
    assert fields[6] == "tcp"
    assert fields[9] == "150"
    assert fields[11] == "SF"


def test_parse_tshark_line_rejects_malformed() -> None:
    assert parse_tshark_line("too\tfew\tfields") is None
    bad_ts = _tshark_line("not-a-number", "10.0.0.1", 1, "10.0.0.2", 80, 6, 10)
    assert parse_tshark_line(bad_ts) is None


def test_parse_tshark_line_uses_udp_ports() -> None:
    line = "\t".join(
        [
            "1.0",
            "10.0.0.1",
            "",
            "5353",
            "8.8.8.8",
            "",
            "53",
            "17",
            "100",
            "0",
            "0",
            "0",
            "0",
        ]
    )
    packet = parse_tshark_line(line)

    assert packet is not None
    assert packet.src_port == 5353
    assert packet.dst_port == 53
    flows = aggregate_flows([packet])
    fields = flows[0].split("\t")
    assert fields[3] == "5353"
    assert fields[5] == "53"
    assert fields[6] == "udp"


def test_parse_tshark_line_rejects_icmp_without_ports() -> None:
    line = "\t".join(
        [
            "1.0",
            "10.0.0.1",
            "",
            "",
            "8.8.8.8",
            "",
            "",
            "1",
            "100",
            "0",
            "0",
            "0",
            "0",
        ]
    )
    assert parse_tshark_line(line) is None


def test_aggregate_flows_uses_each_flow_first_timestamp() -> None:
    packets = [
        parse_tshark_line(_tshark_line(1.0, "10.0.0.1", 1111, "10.0.0.2", 80, 6, 100)),
        parse_tshark_line(_tshark_line(5.0, "10.0.0.3", 3333, "10.0.0.4", 443, 6, 100)),
    ]
    assert all(packet is not None for packet in packets)

    flows = aggregate_flows(packets)

    timestamps = sorted(float(flow.split("\t")[0]) for flow in [flows[0], flows[1]])
    assert timestamps == [1.0, 5.0]


class _FakeStdout:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for line in self._lines:
            yield line


class _FakeProcess:
    def __init__(self, lines: list[bytes]) -> None:
        self.stdout = _FakeStdout(lines)
        self.returncode: int | None = None

    def terminate(self) -> None:
        self.returncode = -15

    async def wait(self) -> int:
        return self.returncode or 0


async def test_live_sensor_run_with_mocked_tshark(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(LiveTsharkSensor, "tshark_available", staticmethod(lambda: True))
    line = _tshark_line(1.0, "10.0.0.1", 1111, "10.0.0.2", 80, 6, 100).encode()
    fake_process = _FakeProcess([line])

    async def fake_exec(*args: object, **kwargs: object) -> _FakeProcess:
        return fake_process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    log_file = tmp_path / "conn.log"
    sensor = LiveTsharkSensor("eth0", log_file, window=0.0)

    await sensor.run()

    content = log_file.read_text()
    assert "10.0.0.1" in content
    assert "10.0.0.2" in content
