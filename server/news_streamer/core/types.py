"""
Core Type Definitions and Exceptions

Service-specific types and exceptions following Kairos fail-fast patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class NewsStreamerError(Exception):
    """Base exception for all news streamer errors."""

    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} [{ctx_str}]"
        return self.message


class ValidationError(NewsStreamerError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        if field:
            ctx["field"] = field
        if value is not None:
            ctx["value"] = repr(value)[:100]  # Truncate long values
        super().__init__(message, ctx)
        self.field = field
        self.value = value


class ConnectionError(NewsStreamerError):
    """Raised when external connection fails."""

    def __init__(
        self,
        message: str,
        service: str,
        retry_count: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx["service"] = service
        ctx["retry_count"] = retry_count
        super().__init__(message, ctx)
        self.service = service
        self.retry_count = retry_count


class AuthenticationError(NewsStreamerError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str,
        service: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx["service"] = service
        super().__init__(message, ctx)
        self.service = service


class PersistenceError(NewsStreamerError):
    """Raised when ClickHouse write fails."""

    def __init__(
        self,
        message: str,
        batch_size: int,
        retry_count: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx["batch_size"] = batch_size
        ctx["retry_count"] = retry_count
        super().__init__(message, ctx)
        self.batch_size = batch_size
        self.retry_count = retry_count


@dataclass
class ReconnectionState:
    """Tracks reconnection attempts for exponential backoff."""

    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    multiplier: float = 2.0
    jitter_factor: float = 0.1
    current_delay: float = field(default=1.0, init=False)
    attempt_count: int = field(default=0, init=False)

    def next_delay(self) -> float:
        """Calculate next delay with exponential backoff and jitter."""
        import random

        delay = self.current_delay

        # Apply jitter (+/- jitter_factor)
        jitter = delay * self.jitter_factor
        delay = delay + random.uniform(-jitter, jitter)

        # Update for next attempt
        self.current_delay = min(
            self.current_delay * self.multiplier,
            self.max_delay_seconds,
        )
        self.attempt_count += 1

        return max(0.1, delay)  # Minimum 100ms

    def reset(self) -> None:
        """Reset state after successful connection."""
        self.current_delay = self.initial_delay_seconds
        self.attempt_count = 0
