from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
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
    erp_api_url: str = Field(default="http://127.0.0.1:8000", validation_alias=AliasChoices("CONSTRUCTION_ERP_API_URL", "ERP_API_URL"))
    erp_service_key: str | None = Field(default=None, validation_alias=AliasChoices("CONSTRUCTION_ERP_SERVICE_KEY", "AI_AGENT_SERVICE_KEY"))
    jwt_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("CONSTRUCTION_JWT_SECRET_KEY", "SECRET_KEY"))
    jwt_algorithm: str = "HS256"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)

        return value

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATHS,
        env_prefix="CONSTRUCTION_",
        extra="ignore",
    )


settings = Settings()