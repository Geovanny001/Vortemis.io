import argparse
import asyncio
import getpass
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.infrastructure.persistence.operator_admin import set_operator_password

DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=None)
    parser.add_argument("--role", choices=["admin", "analyst"], default=None)
    return parser.parse_args()


async def _run(username: str, password: str, role: str | None) -> None:
    engine = create_async_engine(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            created = await set_operator_password(session, username, password, role)
            await session.commit()
        print("created" if created else "updated", username)
    finally:
        await engine.dispose()


def main() -> None:
    args = _parse_args()
    password = args.password or getpass.getpass("New password: ")
    asyncio.run(_run(args.username, password, args.role))


if __name__ == "__main__":
    main()
