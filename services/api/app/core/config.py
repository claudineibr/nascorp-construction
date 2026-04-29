from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


API_ROOT = Path(__file__).resolve().parents[2]
CONSTRUCTION_ROOT = Path(__file__).resolve().parents[4]
EXTERNAL_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = Path(__file__).resolve().parents[6]

ENV_FILE_PATHS = (
    API_ROOT / ".env",
    CONSTRUCTION_ROOT / ".env",
    EXTERNAL_ROOT / ".env",
    WORKSPACE_ROOT / ".env",
)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/nascorp"
    db_schema: str = "construction"
    event_queue_url: str | None = None
    dead_letter_queue_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATHS,
        env_prefix="CONSTRUCTION_",
        extra="ignore",
    )


settings = Settings()