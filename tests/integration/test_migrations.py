from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from vortemis.infrastructure.persistence.models import Base

ROOT = Path(__file__).resolve().parents[2]


def _upgrade(url: str) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def test_migration_creates_the_metadata_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migrated.db"
    _upgrade(f"sqlite+aiosqlite:///{database_path.as_posix()}")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names()) - {"alembic_version"}

        assert tables == set(Base.metadata.tables)

        for table in tables:
            expected = {index.name for index in Base.metadata.tables[table].indexes}
            actual = {index["name"] for index in inspector.get_indexes(table)}

            assert actual == expected
    finally:
        engine.dispose()
