"""
News Streamer Configuration

Centralized configuration following Kairos patterns.
All environment variables MUST be defined here. No os.getenv() calls allowed elsewhere.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


def _require_env(name: str, description: str) -> str:
    """Get a required environment variable or raise ConfigurationError."""
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(
            f"Missing required environment variable: {name}\n"
            f"Description: {description}\n"
            f"Please set this in your .env file or environment."
        )
    return value


def _optional_env(name: str, default: str = "") -> str:
    """Get an optional environment variable with a default."""
    return os.environ.get(name, default)


def _optional_env_int(name: str, default: int) -> int:
    """Get an optional integer environment variable with a default."""
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ConfigurationError(f"Invalid integer value for {name}: {value}")


def _optional_env_bool(name: str, default: bool) -> bool:
    """Get an optional boolean environment variable with a default."""
    value = os.environ.get(name)
    if not value:
        return default
    return value.lower() in ("true", "1", "yes")


@dataclass(frozen=True)
class DBNewsConfig:
    """DBNews WebSocket connection configuration."""
    username: str
    password: str
    ws_base_url: str = "wss://dbws.io"

    @property
    def ws_url(self) -> str:
        """Get the full WebSocket URL with authentication."""
        host = self.ws_base_url.replace("wss://", "").replace("ws://", "")
        protocol = "wss" if self.ws_base_url.startswith("wss://") else "ws"
        return f"{protocol}://{self.username}:{self.password}@{host}/all"


@dataclass(frozen=True)
class ClickHouseConfig:
    """ClickHouse connection configuration."""
    host: str
    port: int
    database: str
    user: str
    password: str
    secure: bool = False

    @property
    def url(self) -> str:
        """Get ClickHouse connection URL."""
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.host}:{self.port}"


@dataclass(frozen=True)
class PostgresConfig:
    """PostgreSQL connection configuration for TagRules."""
    url: str


@dataclass(frozen=True)
class JWTConfig:
    """JWT authentication configuration."""
    secret: str
    issuer: str = "kairos.trade"
    audience: str = "kairos-api"


@dataclass(frozen=True)
class WebSocketServerConfig:
    """WebSocket server configuration for client connections."""
    host: str
    port: int
    jwt: JWTConfig = None


@dataclass(frozen=True)
class BatchConfig:
    """Batching configuration for ClickHouse writes."""
    size: int
    interval_ms: int


@dataclass(frozen=True)
class TaggerConfig:
    """News tagger configuration."""
    use_dbnews_hints: bool


@dataclass(frozen=True)
class PlatformTagsConfig:
    """Platform tags configuration."""
    refresh_interval_ms: int  # How often to reload tags from DB (0 = disabled)


@dataclass(frozen=True)
class Settings:
    """Root configuration container."""
    dbnews: DBNewsConfig
    websocket_server: WebSocketServerConfig

    @property
    def tagger(self) -> TaggerConfig:
        """Get default tagger config for streaming."""
        return TaggerConfig(use_dbnews_hints=True)


def _load_settings() -> Settings:
    """Load all settings from environment variables.

    DBNews credentials are optional — missing values are allowed so that
    --mock mode works without a .env file.  The live feed path in main.py
    will fail later if it actually tries to connect without credentials.
    """
    dbnews = DBNewsConfig(
        username=_optional_env("DBNEWS_USERNAME", ""),
        password=_optional_env("DBNEWS_PASSWORD", ""),
        ws_base_url=_optional_env("DBNEWS_WS_URL", "wss://dbws.io"),
    )

    websocket_server = WebSocketServerConfig(
        host=_optional_env("WS_HOST", "0.0.0.0"),
        port=_optional_env_int("WS_PORT", 8765),
        jwt=None,
    )

    return Settings(
        dbnews=dbnews,
        websocket_server=websocket_server,
    )


settings = _load_settings()
