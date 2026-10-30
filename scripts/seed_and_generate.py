import asyncio
import os
import random
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vortemis.infrastructure.persistence.models import Base, DimMitreTactic

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
SAMPLE_PATH = Path("data/samples/conn_massive.log")
RECORD_COUNT = 5000

_SRC_NETWORKS = ["192.168.1", "192.168.2", "10.0.0", "172.16.0"]
_DST_HOSTS = [
    "142.250.72.14",
    "8.8.8.8",
    "93.184.216.34",
    "10.0.0.5",
    "1.1.1.1",
    "151.101.1.69",
]
_SERVICES = ["ssl", "dns", "http", "ssh", "smtp", "-"]
_PROTOCOLS = ["tcp", "udp"]
_CONN_STATES = ["SF", "S1", "S2", "REJ", "S0"]
_TCP_PORTS = [80, 443, 22, 21, 8080, 445, 3389]
_UDP_PORTS = [53, 123, 67, 161]

_MITRE_TACTICS = [
    ("TA0010", "Exfiltration"),
    ("TA0008", "Lateral Movement"),
    ("TA0011", "Command and Control"),
    ("TA0040", "Impact"),
    ("TA0043", "Reconnaissance"),
]


def _render_header() -> list[str]:
    return [
        "#separator \\x09",
        "#set_separator\t,",
        "#empty_field\t(empty)",
        "#unset_field\t-",
        "#path\tconn",
        "#open\t2024-11-14-00-00-00",
        "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state",
        "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tstring",
    ]


def _build_records(count: int) -> list[str]:
    rng = random.Random(42)
    clock = 1_700_000_000.0
    rows: list[str] = []
    for index in range(count):
        scan_burst = index % 400 < 40
        exfiltration = index % 1200 == 0
        if scan_burst:
            clock += rng.uniform(0.001, 0.004)
        elif exfiltration:
            clock += rng.uniform(0.1, 0.5)
        else:
            clock += rng.uniform(0.05, 2.0)
        if exfiltration:
            orig_bytes = rng.randint(5000, 40000)
        elif scan_burst:
            orig_bytes = rng.randint(40, 120)
        else:
            orig_bytes = rng.randint(50, 2000)
        resp_bytes = rng.randint(40, 3000)
        proto = rng.choice(_PROTOCOLS)
        src_ip = f"{rng.choice(_SRC_NETWORKS)}.{rng.randint(1, 254)}"
        src_port = rng.randint(1024, 65535)
        dst_ip = rng.choice(_DST_HOSTS)
        if scan_burst:
            dst_port = rng.randint(1, 65535)
        else:
            dst_port = rng.choice(_TCP_PORTS if proto == "tcp" else _UDP_PORTS)
        duration = rng.uniform(0.01, 1.5)
        service = rng.choice(_SERVICES)
        conn_state = rng.choice(_CONN_STATES)
        rows.append(
            "\t".join(
                [
                    f"{clock:.6f}",
                    f"C{index + 1:08d}",
                    src_ip,
                    str(src_port),
                    dst_ip,
                    str(dst_port),
                    proto,
                    service,
                    f"{duration:.6f}",
                    str(orig_bytes),
                    str(resp_bytes),
                    conn_state,
                ]
            )
        )
    return rows


def generate_sample_file() -> None:
    content = "\n".join(_render_header() + _build_records(RECORD_COUNT)) + "\n"
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.write_text(content)


async def seed_database() -> None:
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await _seed_mitre_tactics(session)
        await session.commit()
    await engine.dispose()


async def _seed_mitre_tactics(session: AsyncSession) -> None:
    result = await session.execute(select(DimMitreTactic.mitre_id))
    existing = set(result.scalars())
    missing = [
        DimMitreTactic(mitre_id=mitre_id, tactic_name=tactic_name)
        for mitre_id, tactic_name in _MITRE_TACTICS
        if mitre_id not in existing
    ]
    if missing:
        session.add_all(missing)


async def _run() -> None:
    generate_sample_file()
    await seed_database()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
