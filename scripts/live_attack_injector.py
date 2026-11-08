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
    "#open\t2026-11-05-00-00-00",
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state",
    "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tstring",
]

_ATTACKS = ["TA0010", "TA0008", "TA0040", "TA0043", "TA0011"]


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


def _make_flow(attack: str, rng: random.Random, ts: float, uid: str) -> str:
    if attack == "TA0010":
        return _row(
            ts, uid, "10.0.0.5", rng.randint(30000, 60000),
            "185.199.108.153", 443, "tcp", "ssl", rng.uniform(1.0, 4.0),
            rng.randint(25000, 120000), rng.randint(100, 2000), "SF",
        )
    if attack == "TA0008":
        return _row(
            ts, uid, "192.168.1.10", rng.randint(30000, 60000),
            "10.0.0.20", rng.choice([22, 445, 3389]), "tcp", "-",
            rng.uniform(0.1, 1.0), rng.randint(200, 2000), rng.randint(100, 2000), "SF",
        )
    if attack == "TA0040":
        return _row(
            ts, uid, "172.16.0.7", rng.randint(1024, 65535),
            "192.168.1.5", rng.randint(1, 65535), "tcp", "-",
            rng.uniform(0.001, 0.01), rng.randint(40, 120), 0, rng.choice(["RSTO", "RSTR", "S0"]),
        )
    if attack == "TA0043":
        return _row(
            ts, uid, "10.0.0.5", rng.randint(30000, 60000),
            "192.168.1.20", rng.randint(1, 65535), "tcp", "-",
            rng.uniform(0.001, 0.04), 40, 0, rng.choice(["S0", "REJ"]),
        )
    return _row(
        ts, uid, "192.168.1.10", rng.randint(30000, 60000),
        "45.33.32.156", rng.choice([53, 80, 443, 8080]), "tcp", "-",
        rng.uniform(0.05, 1.0), rng.randint(40, 1200), rng.randint(40, 800), "SF",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", default="conn.log")
    parser.add_argument("--attack", default="TA0043", choices=_ATTACKS + ["mixed"])
    parser.add_argument("--rate", type=float, default=1.0)
    args = parser.parse_args()

    path = Path(args.log_file)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(_HEADER) + "\n")

    rng = random.Random()
    clock = time.time()
    uid_counter = 0
    while True:
        attack = rng.choice(_ATTACKS) if args.attack == "mixed" else args.attack
        uid_counter += 1
        if attack == "TA0040":
            clock += rng.uniform(0.0005, 0.002)
        else:
            clock += rng.uniform(0.01, 0.5)
        line = _make_flow(attack, rng, clock, f"C{uid_counter:08d}")
        with path.open("a") as handle:
            handle.write(line + "\n")
        time.sleep(1.0 / args.rate)


if __name__ == "__main__":
    main()
