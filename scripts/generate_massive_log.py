import random
import time
import uuid
from pathlib import Path


def generate_zeek_log() -> None:
    output_dir = Path("data/samples")
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / "conn_massive.log"

    headers = [
        "#separator \\x09",
        "#set_separator\t,",
        "#empty_field\t(empty)",
        "#unset_field\t-",
        "#path\tconn",
        "#open\t2026-10-24-23-00-00",
        "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state\tlocal_orig\tlocal_resp\tmissed_bytes\thistory\torig_pkts\torig_ip_bytes\tresp_pkts\tresp_ip_bytes\ttunnel_parents",
        "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tstring\tbool\tbool\tcount\tstring\tcount\tcount\tcount\tcount\tset[string]",
    ]

    protocols = ["tcp", "udp", "icmp"]
    services = ["http", "dns", "ssl", "-", "ssh"]
    states = ["S0", "S1", "SF", "REJ", "S2", "S3", "RSTO", "RSTR", "SH", "OTH"]

    print("Generating massive Zeek telemetry...")

    with open(file_path, "w", encoding="utf-8") as f:
        for header in headers:
            line = header.replace("\\x09", "\x09") if "#separator" in header else header
            f.write(f"{line}\n")

        start_ts = time.time() - 86400
        for _ in range(10000):
            ts = f"{start_ts + random.uniform(0, 86400):.6f}"
            uid = f"C{uuid.uuid4().hex[:17]}"
            orig_h = f"192.168.1.{random.randint(1, 254)}"
            orig_p = str(random.randint(1024, 65535))
            resp_h = (
                f"{random.randint(1, 254)}.{random.randint(1, 254)}."
                f"{random.randint(1, 254)}.{random.randint(1, 254)}"
            )
            resp_p = str(random.choice([80, 443, 53, 22, 8080]))
            proto = random.choice(protocols)
            service = random.choice(services)
            duration = f"{random.uniform(0.001, 15.0):.6f}"
            orig_b = str(random.randint(0, 5000))
            resp_b = str(random.randint(0, 50000))
            state = random.choice(states)

            row = (
                f"{ts}\t{uid}\t{orig_h}\t{orig_p}\t{resp_h}\t{resp_p}\t"
                f"{proto}\t{service}\t{duration}\t{orig_b}\t{resp_b}\t{state}"
                "\t-\t-\t0\t-\t1\t40\t1\t40\t-"
            )
            f.write(f"{row}\n")

    print(f"Success! 10,000 records saved to {file_path}")


if __name__ == "__main__":
    generate_zeek_log()
