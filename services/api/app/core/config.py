from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


API_ROOT = Path(__file__).resolve().parents[2]
CONSTRUCTION_ROOT = API_ROOT.parents[1] if len(API_ROOT.parents) > 1 else API_ROOT
EXTERNAL_ROOT = API_ROOT.parents[2] if len(API_ROOT.parents) > 2 else CONSTRUCTION_ROOT
WORKSPACE_ROOT = API_ROOT.parents[3] if len(API_ROOT.parents) > 3 else EXTERNAL_ROOT

ENV_FILE_PATHS = (
    API_ROOT / ".env",
    CONSTRUCTION_ROOT / ".env",
    EXTERNAL_ROOT / ".env",
    WORKSPACE_ROOT / ".env",
)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/nascorp"
    db_schema: str = "construction"
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:8001",
            "http://localhost:8001",
            "http://127.0.0.1:8002",
            "http://localhost:8002",
            "http://127.0.0.1:8011",
            "http://localhost:8011",
            "http://127.0.0.1:8085",
            "http://localhost:8085",
        ]
    )
    event_queue_url: str | None = None
    dead_letter_queue_url: str | None = None
    erp_api_url: str = Field(default="http://127.0.0.1:8000", validation_alias=AliasChoices("CONSTRUCTION_ERP_API_URL", "ERP_API_URL"))
    erp_service_key: str | None = Field(default=None, validation_alias=AliasChoices("CONSTRUCTION_ERP_SERVICE_KEY", "CONSTRUCTION_ERP_API_KEY"))
    jwt_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("CONSTRUCTION_JWT_SECRET_KEY", "SECRET_KEY"))
    jwt_algorithm: str = "HS256"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)

        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]

        return value

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATHS,
        env_prefix="CONSTRUCTION_",
        extra="ignore",
    )


settings = Settings()