import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
    model_validator,
)


class MCPServerRegistrationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: HttpUrl
    transport: Literal["streamable_http", "sse"]
    server_fingerprint: str = Field(min_length=64, max_length=64)
    approved_version: str = Field(min_length=1, max_length=120)
    allowed_tools: list[str] = Field(default_factory=list, max_length=100)
    oauth_issuer: HttpUrl | None = None


class MCPServerRegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    transport: str
    server_fingerprint: str
    approved_version: str
    allowed_tools: list[str]
    tool_schema_snapshot: dict[str, object]
    oauth_issuer: str | None
    enabled: bool
    reviewed_at: datetime
    reviewed_by: uuid.UUID


class MCPServerRegistrationListRead(BaseModel):
    registrations: list[MCPServerRegistrationRead]


class MCPServerCredentialConfigure(BaseModel):
    credential_type: Literal["oauth_user_delegated", "oauth_client_credentials"]
    issuer: HttpUrl
    audience: str = Field(min_length=1, max_length=2048)
    scopes: list[str] = Field(min_length=1, max_length=50)
    access_token: SecretStr | None = Field(default=None, max_length=8192)
    refresh_token: SecretStr | None = Field(default=None, max_length=8192)
    expires_at: datetime | None = None
    client_id: str | None = Field(default=None, min_length=1, max_length=255)
    client_secret: SecretStr | None = Field(default=None, max_length=8192)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        cleaned = sorted({scope.strip() for scope in value if scope.strip()})
        if not cleaned or len(cleaned) != len(value):
            raise ValueError("Credential scopes must be non-empty and unique.")
        if any(len(scope) > 128 for scope in cleaned):
            raise ValueError("Credential scopes must be at most 128 characters.")
        return cleaned

    @model_validator(mode="after")
    def validate_credential_shape(self) -> "MCPServerCredentialConfigure":
        if self.credential_type == "oauth_user_delegated":
            if (
                self.access_token is None
                or self.refresh_token is None
                or self.expires_at is None
                or self.client_id is None
            ):
                raise ValueError(
                    "User-delegated credentials require client ID, access token, "
                    "refresh token, and expiry."
                )
            if self.client_secret is not None:
                raise ValueError("User-delegated credentials cannot include a client secret.")
        elif self.client_id is None or self.client_secret is None:
            raise ValueError(
                "Client-credentials authentication requires client ID and client secret."
            )
        elif any(
            value is not None for value in (self.access_token, self.refresh_token, self.expires_at)
        ):
            raise ValueError(
                "Client-credentials authentication cannot persist access or refresh tokens."
            )
        return self


class MCPServerCredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_registration_id: uuid.UUID
    credential_type: str
    issuer: str
    audience: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
