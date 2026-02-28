"""
Stream Protocol Definitions

Abstract interfaces that both the in-memory dev stub and the eventual
C++ pybind11 Redis binding must satisfy. Each agent listener subscribes
to tag-based channels directly — there is no centralised dispatcher.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from agents.schemas import MarketConfig


@runtime_checkable
class StreamProducer(Protocol):
    """Writes messages to a named stream."""

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        """
        Publish a message to the stream.

        Returns the message ID assigned by the stream backend.
        """
        ...


@runtime_checkable
class TaggedStreamConsumer(Protocol):
    """Subscribes to tag-based channels on the Redis stream."""

    async def subscribe(
        self,
        tags: list[str],
        group: str,
        consumer: str,
        callback: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Subscribe to channels for each tag in *tags*.

        When a message is published to any matching tag channel,
        invoke callback(message_id, payload). Runs until cancelled.
        """
        ...

    async def ack(self, tag: str, group: str, message_id: str) -> None:
        """Acknowledge a message as processed."""
        ...


@runtime_checkable
class MarketRegistryReader(Protocol):
    """Read-only view of the market registry, indexed by tags."""

    async def get_all_markets(self) -> list[MarketConfig]:
        """Return all registered markets."""
        ...

    async def get_market(self, address: str) -> MarketConfig | None:
        """Look up a single market by its on-chain address."""
        ...
