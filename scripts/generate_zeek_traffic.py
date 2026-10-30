import random
from pathlib import Path

OUTPUT_PATH = Path("data/samples/conn_realistic.log")
TOTAL_FLOWS = 10000
SEED = 42

_LATERAL_PORTS = [22, 135, 139, 445, 3389, 5985]
_C2_PORTS = [53, 80, 443, 8080, 8443]
_IMPACT_STATES = ["S0", "RSTO", "RSTR", "SH", "OTH"]
_RECON_STATES = ["S0", "REJ"]
_PRIVATE_NETS = ["10.0.0", "172.16.0", "192.168.1"]


def _headers() -> list[str]:
    return [
        "#separator \\x09",
        "#set_separator\t,",
        "#empty_field\t(empty)",
        "#unset_field\t-",
        "#path\tconn",
        "#open\t2026-11-02-00-00-00",
        "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state",
        "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tstring",
    ]


def _row(
    ts: float,
    uid: str,
    orig_h: str,
    orig_p: int,
    resp_h: str,
    resp_p: int,
    proto: str,
    service: str,
    duration: float,
    orig_bytes: int,
    resp_bytes: int,
    state: str,
) -> str:
    return "\t".join(
        [
            f"{ts:.6f}",
            uid,
            orig_h,
            str(orig_p),
            resp_h,
            str(resp_p),
            proto,
            service,
            f"{duration:.6f}",
            str(orig_bytes),
            str(resp_bytes),
            state,
        ]
    )


def _normal_flow(rng: random.Random, uid: str, ts: float) -> str:
    return _row(
        ts=ts,
        uid=uid,
        orig_h=f"{rng.choice(_PRIVATE_NETS)}.{rng.randint(1, 254)}",
        orig_p=rng.randint(1024, 65535),
        resp_h=rng.choice(["142.250.72.14", "8.8.8.8", "93.184.216.34", "1.1.1.1"]),
        resp_p=rng.choice([80, 443, 53]),
        proto=rng.choice(["tcp", "udp"]),
        service=rng.choice(["http", "dns", "ssl", "-"]),
        duration=rng.uniform(0.01, 3.0),
        orig_bytes=rng.randint(50, 3000),
        resp_bytes=rng.randint(100, 8000),
        state=rng.choice(["SF", "S1", "S2"]),
    )


def _exfil_flow(rng: random.Random, uid: str, ts: float) -> str:
    return _row(
        ts=ts,
        uid=uid,
        orig_h=f"10.0.0.{rng.randint(1, 254)}",
        orig_p=rng.randint(1024, 65535),
        resp_h=rng.choice(["185.199.108.153", "151.101.1.69"]),
        resp_p=443,
        proto="tcp",
        service="ssl",
        duration=rng.uniform(1.0, 5.0),
        orig_bytes=rng.randint(25000, 120000),
        resp_bytes=rng.randint(200, 3000),
        state="SF",
    )


def _lateral_flow(rng: random.Random, uid: str, ts: float) -> str:
    return _row(
        ts=ts,
        uid=uid,
        orig_h=f"192.168.1.{rng.randint(1, 254)}",
        orig_p=rng.randint(1024, 65535),
        resp_h=f"10.0.0.{rng.randint(1, 254)}",
        resp_p=rng.choice(_LATERAL_PORTS),
        proto="tcp",
        service="-",
        duration=rng.uniform(0.05, 1.5),
        orig_bytes=rng.randint(200, 2000),
        resp_bytes=rng.randint(100, 3000),
        state="SF",
    )


def _impact_flow(rng: random.Random, uid: str, ts: float) -> str:
    return _row(
        ts=ts,
        uid=uid,
        orig_h="172.16.0.7",
        orig_p=rng.randint(1024, 65535),
        resp_h=f"192.168.1.{rng.randint(1, 254)}",
        resp_p=rng.randint(1, 65535),
        proto="tcp",
        service="-",
        duration=rng.uniform(0.001, 0.01),
        orig_bytes=rng.randint(40, 120),
        resp_bytes=0,
        state=rng.choice(_IMPACT_STATES),
    )


def _recon_flow(rng: random.Random, uid: str, ts: float) -> str:
    return _row(
        ts=ts,
        uid=uid,
        orig_h=f"10.0.0.{rng.randint(1, 254)}",
        orig_p=rng.randint(1024, 65535),
        resp_h=f"192.168.1.{rng.randint(1, 254)}",
        resp_p=rng.randint(1, 65535),
        proto="tcp",
        service="-",
        duration=rng.uniform(0.001, 0.04),
        orig_bytes=40,
        resp_bytes=0,
        state=rng.choice(_RECON_STATES),
    )


def _c2_flow(rng: random.Random, uid: str, ts: float) -> str:
    return _row(
        ts=ts,
        uid=uid,
        orig_h=f"192.168.1.{rng.randint(1, 254)}",
        orig_p=rng.randint(1024, 65535),
        resp_h=rng.choice(["45.33.32.156", "104.244.42.129"]),
        resp_p=rng.choice(_C2_PORTS),
        proto="tcp",
        service="-",
        duration=rng.uniform(0.05, 1.0),
        orig_bytes=rng.randint(40, 1200),
        resp_bytes=rng.randint(40, 800),
        state="SF",
    )


def generate() -> None:
    rng = random.Random(SEED)
    rows: list[str] = []
    clock = 1_760_000_000.0
    uid_counter = 0

    for _ in range(200):
        clock += rng.uniform(0.2, 2.0)
        uid_counter += 1
        rows.append(_exfil_flow(rng, f"C{uid_counter:08d}", clock))

    for _ in range(200):
        clock += rng.uniform(0.2, 2.0)
        uid_counter += 1
        rows.append(_lateral_flow(rng, f"C{uid_counter:08d}", clock))

    for _ in range(200):
        clock += rng.uniform(0.001, 0.002)
        uid_counter += 1
        rows.append(_impact_flow(rng, f"C{uid_counter:08d}", clock))

    for _ in range(200):
        clock += rng.uniform(0.01, 0.04)
        uid_counter += 1
        rows.append(_recon_flow(rng, f"C{uid_counter:08d}", clock))

    for _ in range(200):
        clock += rng.uniform(0.01, 0.05)
        uid_counter += 1
        rows.append(_c2_flow(rng, f"C{uid_counter:08d}", clock))

    for _ in range(TOTAL_FLOWS - 1000):
        clock += rng.uniform(0.05, 2.0)
        uid_counter += 1
        rows.append(_normal_flow(rng, f"C{uid_counter:08d}", clock))

    content = "\n".join(_headers() + rows) + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content)
    print(f"Generated {TOTAL_FLOWS} flows in {OUTPUT_PATH}")


if __name__ == "__main__":
    generate()
