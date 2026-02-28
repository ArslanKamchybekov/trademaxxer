"""
In-Memory Stream Stub

asyncio.Queue-based implementation of the stream protocols for local
development. Swap for the C++ pybind11 binding with zero changes to
dispatcher / executor code.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any, Awaitable, Callable

from agents.schemas import MarketConfig

logger = logging.getLogger(__name__)


class InMemoryStream:
    """
    Dev stub that satisfies StreamProducer, StreamConsumer, and
    MarketRegistryReader simultaneously.

    Usage:
        stream = InMemoryStream()
        stream.seed_markets([market_a, market_b])

        # Dispatcher wires stream as consumer, producer, and registry
        dispatcher = AgentDispatcher(
            consumer=stream,
            registry=stream,
            producer=stream,
        )
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[tuple[str, dict[str, Any]]]] = (
            defaultdict(asyncio.Queue)
        )
        self._messages: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        self._acked: set[str] = set()

        self._markets: dict[str, MarketConfig] = {}
        self._tag_index: dict[str, set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # MarketRegistryReader
    # ------------------------------------------------------------------

    def seed_markets(self, markets: list[MarketConfig]) -> None:
        """Pre-load markets for local development."""
        for m in markets:
            self._markets[m.address] = m
            for tag in m.tags:
                self._tag_index[tag].add(m.address)
        logger.info(
            f"Seeded {len(markets)} markets across {len(self._tag_index)} tags"
        )

    async def get_markets_by_tags(self, tags: list[str]) -> list[MarketConfig]:
        addresses: set[str] = set()
        for tag in tags:
            addresses |= self._tag_index.get(tag, set())
        return [self._markets[a] for a in addresses if a in self._markets]

    async def get_market(self, address: str) -> MarketConfig | None:
        return self._markets.get(address)

    # ------------------------------------------------------------------
    # StreamProducer
    # ------------------------------------------------------------------

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        message_id = str(uuid.uuid4())
        entry = (message_id, payload)
        self._messages[stream].append(entry)
        await self._queues[stream].put(entry)
        logger.debug(f"Published to {stream}: {message_id}")
        return message_id

    # ------------------------------------------------------------------
    # StreamConsumer
    # ------------------------------------------------------------------

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        callback: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Block and deliver messages to callback until cancelled.

        In this stub, consumer groups are not enforced — every consumer
        sees every message. The real C++ binding handles group semantics.
        """
        logger.info(f"Consumer {group}/{consumer} listening on {stream}")
        q = self._queues[stream]
        while True:
            message_id, payload = await q.get()
            try:
                await callback(message_id, payload)
            except Exception:
                logger.exception(
                    f"Consumer {group}/{consumer} callback failed for {message_id}"
                )

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        self._acked.add(message_id)

    # ------------------------------------------------------------------
    # Introspection (for tests)
    # ------------------------------------------------------------------

    def get_all_messages(self, stream: str) -> list[tuple[str, dict[str, Any]]]:
        """Return all messages published to a stream (ordered)."""
        return list(self._messages.get(stream, []))

    @property
    def acked_ids(self) -> frozenset[str]:
        return frozenset(self._acked)

    @property
    def market_count(self) -> int:
        return len(self._markets)
