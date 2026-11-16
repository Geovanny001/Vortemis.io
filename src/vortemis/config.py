import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
LOG_FILE_ENV = "LOG_FILE"
DEFAULT_LOG_FILE = "conn.log"
MODEL_PATH_ENV = "MODEL_PATH"
DEFAULT_MODEL_PATH = "models/vortemis_ae.pt"
EPSILON_ENV = "EPSILON"
DEFAULT_EPSILON = 0.70
CONTINUOUS_MODE_ENV = "CONTINUOUS_MODE"
API_CORS_ENV = "VORTEMIS_CORS_ORIGINS"
API_ACCESS_TTL_ENV = "VORTEMIS_ACCESS_TTL_MINUTES"
API_REFRESH_TTL_ENV = "VORTEMIS_REFRESH_TTL_DAYS"
DEFAULT_ACCESS_TTL_MINUTES = 15.0
DEFAULT_REFRESH_TTL_DAYS = 30.0


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    log_file: Path
    model_path: Path
    epsilon: float
    continuous_mode: bool

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL),
            log_file=Path(os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE)),
            model_path=Path(os.getenv(MODEL_PATH_ENV, DEFAULT_MODEL_PATH)),
            epsilon=float(os.getenv(EPSILON_ENV, str(DEFAULT_EPSILON))),
            continuous_mode=os.getenv(CONTINUOUS_MODE_ENV, "false").lower() == "true",
        )


@dataclass(frozen=True, slots=True)
class ApiSettings:
    cors_origins: tuple[str, ...]
    access_ttl: timedelta
    refresh_ttl: timedelta

    @classmethod
    def from_env(cls) -> ApiSettings:
        raw = os.getenv(API_CORS_ENV, "")
        origins = tuple(
            origin.strip() for origin in raw.split(",") if origin.strip()
        )
        access_minutes = float(
            os.getenv(API_ACCESS_TTL_ENV, str(DEFAULT_ACCESS_TTL_MINUTES))
        )
        refresh_days = float(
            os.getenv(API_REFRESH_TTL_ENV, str(DEFAULT_REFRESH_TTL_DAYS))
        )
        return cls(
            cors_origins=origins,
            access_ttl=timedelta(minutes=access_minutes),
            refresh_ttl=timedelta(days=refresh_days),
        )
