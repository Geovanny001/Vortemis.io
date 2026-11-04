import os
from dataclasses import dataclass
from pathlib import Path

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
LOG_FILE_ENV = "LOG_FILE"
DEFAULT_LOG_FILE = "conn.log"
MODEL_PATH_ENV = "MODEL_PATH"
DEFAULT_MODEL_PATH = "models/vortemis_ae.pt"
EPSILON_ENV = "EPSILON"
DEFAULT_EPSILON = 0.70


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    log_file: Path
    model_path: Path
    epsilon: float

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL),
            log_file=Path(os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE)),
            model_path=Path(os.getenv(MODEL_PATH_ENV, DEFAULT_MODEL_PATH)),
            epsilon=float(os.getenv(EPSILON_ENV, str(DEFAULT_EPSILON))),
        )
