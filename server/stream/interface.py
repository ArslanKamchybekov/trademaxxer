"""
Stream Protocol Definitions

Abstract interfaces that both the in-memory dev stub and the eventual
C++ pybind11 Redis binding must satisfy. All consumers of the stream
(dispatcher, executor, monitor) depend only on these protocols.
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
class StreamConsumer(Protocol):
    """Consumes messages from a named stream using consumer groups."""

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        callback: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Begin consuming messages from *stream* as part of *group*.

        For each message, invoke callback(message_id, payload).
        Runs until cancelled.
        """
        ...

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        """Acknowledge a message as processed."""
        ...


@runtime_checkable
class MarketRegistryReader(Protocol):
    """Read-only view of the market registry, indexed by tags."""

    async def get_markets_by_tags(self, tags: list[str]) -> list[MarketConfig]:
        """
        Return all markets whose tag set intersects with *tags*.

        A market with tags ("fed", "macro") is returned if *tags*
        contains "fed" OR "macro" (union match).
        """
        ...

    async def get_market(self, address: str) -> MarketConfig | None:
        """Look up a single market by its on-chain address."""
        ...
