import argparse
import random
import time
from pathlib import Path

_HEADER = [
    "#separator \\x09",
    "#set_separator\t,",
    "#empty_field\t(empty)",
    "#unset_field\t-",
    "#path\tconn",
    "#open\t2026-11-19-00-00-00",
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice"
    "\tduration\torig_bytes\tresp_bytes\tconn_state",
    "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount"
    "\tcount\tstring",
]

_TACTICS = ["TA0043", "TA0008", "TA0011", "TA0010", "TA0040"]

_BENIGN_HOSTS = ["192.168.2.11", "192.168.2.24"]
_BENIGN_TARGETS = ["142.250.72.14", "151.101.1.69", "8.8.8.8", "1.1.1.1"]
_EXFIL_SRC = "10.0.0.5"
_LATERAL_SRC = "192.168.1.10"
_IMPACT_SRC = "172.16.0.7"
_RECON_SRC = "10.0.0.9"
_C2_SRC = "192.168.1.30"


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


def _ensure_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_HEADER) + "\n")


def _append(path: Path, line: str) -> None:
    with path.open("a") as handle:
        handle.write(line + "\n")


def _benign(rng: random.Random, ts: float, uid: int, host: str) -> str:
    orig = rng.randint(110, 520)
    resp = max(90, int(orig * rng.uniform(0.8, 2.6)))
    return _row(
        ts,
        f"C{uid:08d}",
        host,
        rng.randint(30000, 60999),
        rng.choice(_BENIGN_TARGETS),
        rng.choice([443, 80, 53]),
        "tcp",
        "-",
        rng.uniform(0.3, 1.5),
        orig,
        resp,
        "SF",
    )


def _recon(ts: float, uid: int, src: str, rng: random.Random) -> str:
    return _row(
        ts,
        f"C{uid:08d}",
        src,
        rng.randint(30000, 60999),
        "192.168.1.20",
        rng.randint(49152, 65535),
        "tcp",
        "-",
        0.01,
        40,
        0,
        "REJ",
    )


def _exfil(rng: random.Random, ts: float, uid: int) -> str:
    return _row(
        ts,
        f"C{uid:08d}",
        _EXFIL_SRC,
        rng.randint(30000, 60999),
        "185.199.108.153",
        443,
        "tcp",
        "ssl",
        rng.uniform(1.0, 4.0),
        rng.randint(30000, 120000),
        rng.randint(50, 700),
        "SF",
    )


def _lateral(rng: random.Random, ts: float, uid: int) -> str:
    return _row(
        ts,
        f"C{uid:08d}",
        _LATERAL_SRC,
        rng.randint(30000, 60999),
        rng.choice(["10.0.0.21", "10.0.0.22"]),
        rng.choice([445, 3389, 22]),
        "tcp",
        "-",
        rng.uniform(600.0, 3600.0),
        rng.randint(900, 1800),
        rng.randint(600, 1200),
        "SF",
    )


def _c2(rng: random.Random, ts: float, uid: int) -> str:
    return _row(
        ts,
        f"C{uid:08d}",
        _C2_SRC,
        rng.randint(30000, 60999),
        "45.33.32.156",
        rng.choice([443, 8080, 8443, 53]),
        "tcp",
        "-",
        rng.uniform(30.0, 120.0),
        rng.randint(80, 400),
        rng.randint(2000, 8000),
        "SF",
    )


def _impact(rng: random.Random, base: float, uid: int) -> list[str]:
    trigger = _recon(base, uid, _IMPACT_SRC, rng)
    attack = _row(
        base + 0.0005,
        f"C{uid + 1:08d}",
        _IMPACT_SRC,
        rng.randint(1024, 65535),
        "192.168.1.5",
        12345,
        "tcp",
        "-",
        0.004,
        60,
        0,
        "RSTO",
    )
    return [trigger, attack]


def _warmup(ts: float, uid: int, host: str, rng: random.Random) -> str:
    return _recon(ts, uid, host, rng)


def _emit_attack(
    path: Path,
    tactic: str,
    rng: random.Random,
    base: float,
    uid: int,
) -> int:
    if tactic == "TA0010":
        _append(path, _exfil(rng, base, uid))
        return uid + 1
    if tactic == "TA0011":
        _append(path, _c2(rng, base, uid))
        return uid + 1
    if tactic == "TA0008":
        _append(path, _lateral(rng, base, uid))
        return uid + 1
    if tactic == "TA0040":
        for line in _impact(rng, base, uid):
            _append(path, line)
        return uid + 2
    _append(path, _recon(base, uid, _RECON_SRC, rng))
    return uid + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", default="data/samples/conn_massive.log")
    parser.add_argument("--cycle-seconds", type=float, default=40.0)
    parser.add_argument("--benign-interval", type=float, default=0.15)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    path = Path(args.log_file)
    _ensure_header(path)

    rng = random.Random()
    attack_every = max(args.cycle_seconds / len(_TACTICS), 1.0)
    last_attack = 0.0
    index = 0
    uid = 0

    for host in _BENIGN_HOSTS:
        uid += 1
        _append(path, _warmup(time.time(), uid, host, rng))
        time.sleep(args.benign_interval)

    while True:
        now = time.time()
        uid += 1
        host = _BENIGN_HOSTS[uid % len(_BENIGN_HOSTS)]
        _append(path, _benign(rng, now, uid, host))
        if now - last_attack >= attack_every:
            tactic = _TACTICS[index % len(_TACTICS)]
            uid = _emit_attack(path, tactic, rng, now, uid)
            last_attack = now
            index += 1
            if args.once and index >= len(_TACTICS):
                break
        time.sleep(args.benign_interval)


if __name__ == "__main__":
    main()
