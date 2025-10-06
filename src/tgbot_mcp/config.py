"""Configuration models for the Telegram MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramSettings(BaseSettings):
    """Settings that control the Telegram connection."""

    api_id: int = Field(..., description="Telegram application API ID")
    api_hash: str = Field(..., description="Telegram application API hash")
    session_file: Path = Field(
        default=Path("./telegram.session"),
        description="Filesystem path to the Telethon session file",
    )
    session_string: str | None = Field(
        default=None,
        description="Optional Telethon StringSession that overrides the session file",
    )
    request_retries: int = Field(
        default=5,
        ge=0,
        description="How many times Telethon should retry failed API requests",
    )
    default_page_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Default number of items returned by list/search tools",
    )
    default_transport: Literal["stdio", "sse", "streamable-http"] = Field(
        default="stdio",
        description="Transport used when running without explicit --transport flag",
    )

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _validate_session_source(self) -> "TelegramSettings":
        if not self.session_string and not self.session_file:
            raise ValueError("Either session_string or session_file must be provided")
        if self.session_file:
            self.session_file = self.session_file.expanduser().resolve()
        return self


class SearchMessagesRequest(BaseModel):
    chat: str = Field(..., description="Chat identifier (username, title, or internal ID)")
    query: str = Field(..., min_length=1, description="Full-text search query")
    limit: int = Field(20, ge=1, le=500, description="Maximum number of messages to return")
    offset_id: int | None = Field(
        default=None,
        description="Continue searching before this message ID (for pagination)",
    )


class FetchMessagesRequest(BaseModel):
    chat: str = Field(..., description="Chat identifier (username, title, or internal ID)")
    limit: int = Field(20, ge=1, le=200, description="Number of messages to fetch")
    offset_id: int | None = Field(
        default=None,
        description="Fetch messages older than this ID (exclusive)",
    )


class SendMessageRequest(BaseModel):
    chat: str = Field(..., description="Chat identifier (username, title, or internal ID)")
    message: str = Field(..., min_length=1, description="Message body to send")
    reply_to: int | None = Field(default=None, description="Optional message ID to reply to")


class ListDialogsRequest(BaseModel):
    limit: int = Field(50, ge=1, le=200, description="Maximum dialogs to return")
    search: str | None = Field(default=None, description="Optional search term to filter dialog titles")
    include_private: bool = Field(
        default=False,
        description="Whether to include direct message dialogs (default: only groups/channels)",
    )
    include_channels: bool = Field(
        default=True,
        description="Whether to include broadcast channels along with groups",
    )


class GetChatRequest(BaseModel):
    chat: str = Field(..., description="Chat identifier (username, title, or internal ID)")


def load_settings() -> TelegramSettings:
    """Load Telegram settings and surface validation errors nicely."""

    try:
        return TelegramSettings()
    except ValidationError as exc:  # pragma: no cover - convenience wrapper
        errors = exc.errors()
        details = "; ".join(
            f"{error['loc'][0]}: {error['msg']}" for error in errors if error.get("loc")
        )
        raise RuntimeError(f"Invalid Telegram configuration: {details}") from exc
