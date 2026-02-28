"""
News Streamer Core Utilities

Service-specific utilities following Kairos patterns.
"""
from news_streamer.core.types import (
    AuthenticationError,
    ConnectionError,
    NewsStreamerError,
    PersistenceError,
    ReconnectionState,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "ConnectionError",
    "NewsStreamerError",
    "PersistenceError",
    "ReconnectionState",
    "ValidationError",
]
