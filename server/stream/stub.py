"""
In-Memory Stream Stub

asyncio.Queue-based implementation of the stream protocols for local
development. Models tag-based channels: publishing to a tag delivers
to all subscribers of that tag. Swap for the C++ pybind11 binding with
zero changes to listener code.
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
    Dev stub that satisfies StreamProducer, TaggedStreamConsumer, and
    MarketRegistryReader simultaneously.

    Tag routing:
        publish_to_tags(["fed", "macro"], payload)
          → delivers to every subscriber whose tag set includes "fed" OR "macro"

        subscribe(["fed", "macro"], ..., callback)
          → callback fires for messages on "fed" channel OR "macro" channel
    """

    def __init__(self) -> None:
        # tag -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[tuple[str, dict[str, Any]]]]] = (
            defaultdict(list)
        )
        self._messages: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        self._acked: set[str] = set()

        # Named stream (for decisions:raw etc.)
        self._stream_queues: dict[str, asyncio.Queue[tuple[str, dict[str, Any]]]] = (
            defaultdict(asyncio.Queue)
        )
        self._stream_messages: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

        # Market registry
        self._markets: dict[str, MarketConfig] = {}

    # ------------------------------------------------------------------
    # MarketRegistryReader
    # ------------------------------------------------------------------

    def seed_markets(self, markets: list[MarketConfig]) -> None:
        """Pre-load markets for local development."""
        for m in markets:
            self._markets[m.address] = m
        logger.info(f"Seeded {len(markets)} markets")

    async def get_all_markets(self) -> list[MarketConfig]:
        return list(self._markets.values())

    async def get_market(self, address: str) -> MarketConfig | None:
        return self._markets.get(address)

    # ------------------------------------------------------------------
    # Tag-based pub/sub (for news channels)
    # ------------------------------------------------------------------

    async def publish_to_tags(
        self, tags: list[str], payload: dict[str, Any]
    ) -> str:
        """
        Publish a message to every tag channel in *tags*.

        Each subscriber whose subscription includes any of these tags
        receives the message exactly once (deduped by message_id).
        """
        message_id = str(uuid.uuid4())
        entry = (message_id, payload)

        delivered_to: set[int] = set()
        for tag in tags:
            self._messages[tag].append(entry)
            for q in self._subscribers.get(tag, []):
                q_id = id(q)
                if q_id not in delivered_to:
                    await q.put(entry)
                    delivered_to.add(q_id)

        logger.debug(
            f"Published {message_id} to tags {tags} → "
            f"{len(delivered_to)} subscriber(s)"
        )
        return message_id

    async def subscribe(
        self,
        tags: list[str],
        group: str,
        consumer: str,
        callback: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Subscribe to tag channels. Runs until cancelled.

        A single queue is registered for all tags so the subscriber
        sees each message at most once even if it matches multiple tags.
        """
        q: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        for tag in tags:
            self._subscribers[tag].append(q)

        logger.info(f"Subscriber {group}/{consumer} listening on tags {tags}")

        try:
            while True:
                message_id, payload = await q.get()
                try:
                    await callback(message_id, payload)
                except Exception:
                    logger.exception(
                        f"Subscriber {group}/{consumer} callback failed "
                        f"for {message_id}"
                    )
        finally:
            for tag in tags:
                try:
                    self._subscribers[tag].remove(q)
                except ValueError:
                    pass

    async def ack(self, tag: str, group: str, message_id: str) -> None:
        self._acked.add(message_id)

    # ------------------------------------------------------------------
    # StreamProducer (for decisions:raw etc.)
    # ------------------------------------------------------------------

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        message_id = str(uuid.uuid4())
        entry = (message_id, payload)
        self._stream_messages[stream].append(entry)
        logger.debug(f"Published to {stream}: {message_id}")
        return message_id

    # ------------------------------------------------------------------
    # Introspection (for tests)
    # ------------------------------------------------------------------

    def get_tag_messages(self, tag: str) -> list[tuple[str, dict[str, Any]]]:
        """Return all messages published to a tag channel."""
        return list(self._messages.get(tag, []))

    def get_stream_messages(self, stream: str) -> list[tuple[str, dict[str, Any]]]:
        """Return all messages published to a named stream."""
        return list(self._stream_messages.get(stream, []))

    @property
    def acked_ids(self) -> frozenset[str]:
        return frozenset(self._acked)

    @property
    def market_count(self) -> int:
        return len(self._markets)
