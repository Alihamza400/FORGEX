from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ForgeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API
    api_host: str = Field(default="0.0.0.0", alias="FORGE_API_HOST")
    api_port: int = Field(default=8000, alias="FORGE_API_PORT", ge=1024, le=65535)
    api_secret_key: str = Field(default="", alias="FORGE_API_SECRET_KEY")
    api_url: str = Field(default="http://localhost:8000", alias="FORGE_API_URL")

    # Logging
    log_level: str = Field(default="INFO", alias="FORGE_LOG_LEVEL")
    log_json: bool = Field(default=False, alias="FORGE_LOG_JSON")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://forge:forge_secret@localhost:5432/forge",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    # Qdrant
    qdrant_url: str = Field(
        default="http://localhost:6333",
        alias="QDRANT_URL",
    )

    # MinIO
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="forge", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="forge_secret", alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    minio_default_bucket: str = Field(default="forge", alias="MINIO_DEFAULT_BUCKET")

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_BASE_URL",
    )
    ollama_default_model: str = Field(
        default="llama3.2:3b",
        alias="FORGE_DEFAULT_MODEL",
    )

    # Paths
    data_dir: Path = Field(
        default=Path("/var/lib/forge"),
        alias="FORGE_DATA_DIR",
    )

    # Security
    token_expire_minutes: int = Field(default=1440, alias="FORGE_TOKEN_EXPIRE_MINUTES")
    rate_limit_per_minute: int = Field(default=60, alias="FORGE_RATE_LIMIT_PER_MINUTE")

    # Observability
    otlp_endpoint: str | None = Field(default=None, alias="FORGE_OTLP_ENDPOINT")
    otel_console_export: bool = Field(default=False, alias="FORGE_OTEL_CONSOLE_EXPORT")
    metrics_enabled: bool = Field(default=True, alias="FORGE_METRICS_ENABLED")
    metrics_port: int = Field(default=9090, alias="FORGE_METRICS_PORT", ge=1024, le=65535)
    service_name: str = Field(default="forge", alias="FORGE_SERVICE_NAME")
    tracing_enabled: bool = Field(default=True, alias="FORGE_TRACING_ENABLED")


settings = ForgeSettings()
