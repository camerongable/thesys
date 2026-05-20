from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Thesys API"
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+psycopg://thesys:thesys@localhost:5432/thesys",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    litellm_base_url: str = Field(
        default="http://localhost:4000",
        validation_alias="LITELLM_BASE_URL",
    )

    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias="S3_ENDPOINT_URL",
    )
    s3_access_key_id: str = Field(default="minioadmin", validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="minioadmin", validation_alias="S3_SECRET_ACCESS_KEY")
    s3_bucket: str = Field(default="thesys-local", validation_alias="S3_BUCKET")

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
