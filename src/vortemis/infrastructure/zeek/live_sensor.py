import asyncio
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles

_TSHARK_FIELDS = [
    "frame.time_epoch",
    "ip.src",
    "tcp.srcport",
    "udp.srcport",
    "ip.dst",
    "tcp.dstport",
    "udp.dstport",
    "ip.proto",
    "frame.len",
    "tcp.flags.syn",
    "tcp.flags.ack",
    "tcp.flags.reset",
    "tcp.flags.fin",
]

_ZEK_HEADER = [
    "#separator \\x09",
    "#set_separator\t,",
    "#empty_field\t(empty)",
    "#unset_field\t-",
    "#path\tconn",
    "#open\t2026-11-05-00-00-00",
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state",
    "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tstring",
]


@dataclass(frozen=True, slots=True)
class Packet:
    ts: float
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    proto: int
    length: int
    syn: bool
    ack: bool
    reset: bool
    fin: bool


@dataclass(slots=True)
class _FlowAccumulator:
    first_ts: float
    last_ts: float = field(init=False)
    orig_bytes: int = 0
    syn: bool = False
    ack: bool = False
    reset: bool = False
    fin: bool = False

    def __post_init__(self) -> None:
        self.last_ts = self.first_ts

    def add(self, packet: Packet) -> None:
        self.last_ts = max(self.last_ts, packet.ts)
        self.orig_bytes += packet.length
        self.syn = self.syn or packet.syn
        self.ack = self.ack or packet.ack
        self.reset = self.reset or packet.reset
        self.fin = self.fin or packet.fin


def parse_tshark_line(line: str) -> Packet | None:
    parts = line.rstrip("\r\n").split("\t")
    if len(parts) < 13:
        return None
    try:
        ts = float(parts[0])
        src_ip = parts[1]
        src_port = int(parts[2] or 0)
        dst_ip = parts[4]
        dst_port = int(parts[5] or 0)
        proto = int(parts[7] or 0)
        length = int(parts[8] or 0)
    except ValueError:
        return None
    if not src_ip or not dst_ip:
        return None
    flags = parts[9:13]
    return Packet(
        ts=ts,
        src_ip=src_ip,
        src_port=src_port,
        dst_ip=dst_ip,
        dst_port=dst_port,
        proto=proto,
        length=length,
        syn=flags[0] == "1",
        ack=flags[1] == "1",
        reset=flags[2] == "1",
        fin=flags[3] == "1",
    )


def _proto_name(proto: int) -> str:
    if proto == 6:
        return "tcp"
    if proto == 17:
        return "udp"
    if proto == 1:
        return "icmp"
    return "tcp"


def _deduce_state(accumulator: _FlowAccumulator) -> str:
    if accumulator.reset:
        return "RSTO"
    if accumulator.ack or accumulator.fin:
        return "SF"
    if accumulator.syn:
        return "S0"
    return "OTH"


def _render_flow(ts: float, key: tuple, accumulator: _FlowAccumulator) -> str:
    src_ip, src_port, dst_ip, dst_port, proto = key
    duration = accumulator.last_ts - accumulator.first_ts
    return "\t".join(
        [
            f"{ts:.6f}",
            f"C{abs(hash(key)) % 10**9:09d}",
            src_ip,
            str(src_port or 0),
            dst_ip,
            str(dst_port or 0),
            _proto_name(proto),
            "-",
            f"{duration:.6f}",
            str(accumulator.orig_bytes),
            "0",
            _deduce_state(accumulator),
        ]
    )


def aggregate_flows(packets: list[Packet]) -> list[str]:
    groups: dict[tuple, _FlowAccumulator] = {}
    for packet in packets:
        key = (
            packet.src_ip,
            packet.src_port,
            packet.dst_ip,
            packet.dst_port,
            packet.proto,
        )
        if key not in groups:
            groups[key] = _FlowAccumulator(first_ts=packet.ts)
        groups[key].add(packet)
    return [_render_flow(packet.ts, key, acc) for key, acc in groups.items()]


class LiveTsharkSensor:
    def __init__(self, interface: str, log_file: Path, window: float = 2.0) -> None:
        self._interface = interface
        self._log_file = log_file
        self._window = window
        self._accumulator: dict[tuple, _FlowAccumulator] = {}

    @staticmethod
    def tshark_available() -> bool:
        return shutil.which("tshark") is not None

    async def _ensure_header(self) -> None:
        if self._log_file.exists():
            return
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._log_file, "w") as handle:
            await handle.write("\n".join(_ZEK_HEADER) + "\n")

    async def run(self) -> None:
        if not self.tshark_available():
            return
        await self._ensure_header()
        process = await asyncio.create_subprocess_exec(
            "tshark",
            "-i",
            self._interface,
            "-l",
            "-n",
            "-T",
            "fields",
            "-E",
            "separator=\t",
            *[f"-e{field}" for field in _TSHARK_FIELDS],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert process.stdout is not None
        try:
            window_start = time.monotonic()
            pending: list[Packet] = []
            async for raw_line in process.stdout:
                packet = parse_tshark_line(raw_line.decode(errors="replace"))
                if packet is None:
                    continue
                pending.append(packet)
                now = time.monotonic()
                if now - window_start >= self._window:
                    await self._flush(pending)
                    pending = []
                    window_start = now
            if pending:
                await self._flush(pending)
        finally:
            if process.returncode is None:
                process.terminate()
            await process.wait()

    async def _flush(self, packets: list[Packet]) -> None:
        if not packets:
            return
        await self._ensure_header()
        async with aiofiles.open(self._log_file, "a") as handle:
            for line in aggregate_flows(packets):
                await handle.write(line + "\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", default="wlan0")
    parser.add_argument("--log-file", default="conn.log")
    args = parser.parse_args()
    sensor = LiveTsharkSensor(args.interface, Path(args.log_file))
    asyncio.run(sensor.run())


if __name__ == "__main__":
    main()
