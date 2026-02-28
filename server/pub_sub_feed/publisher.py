"""
Feed Publisher

Generic Redis pub/sub publisher. Accepts an explicit channel (or list of
channels) and a plain dict payload — no domain knowledge required.

Usage:
    publisher = FeedPublisher(redis_url="redis://localhost:6379/0")
    await publisher.connect()

    await publisher.publish("my:channel", {"key": "value"})
    await publisher.publish_many(["chan:a", "chan:b"], {"key": "value"})

    await publisher.close()

Context manager usage:
    async with FeedPublisher(redis_url=...) as pub:
        await pub.publish("my:channel", data)
"""
from __future__ import annotations

import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .serializer import SerializationError, serialize

logger = logging.getLogger(__name__)


class PublisherError(Exception):
    """Raised when a publish operation fails."""


class FeedPublisher:
    """
    Publishes JSON-serializable dicts to Redis pub/sub channels.

    The caller is responsible for deciding which channels to publish to.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Redis | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the Redis connection."""
        self._redis = Redis.from_url(self._redis_url, decode_responses=False)
        try:
            await self._redis.ping()
            logger.info("FeedPublisher connected to Redis at %s", self._redis_url)
        except RedisError as exc:
            raise PublisherError(f"Cannot connect to Redis: {exc}") from exc

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("FeedPublisher disconnected from Redis")

    async def __aenter__(self) -> FeedPublisher:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ── Publish ───────────────────────────────────────────────────────────────

    async def publish(self, channel: str, data: dict[str, Any]) -> int:
        """
        Publish data to a single channel.

        Args:
            channel: The Redis channel name.
            data:    JSON-serializable dict payload.

        Returns:
            Number of subscribers that received the message.

        Raises:
            PublisherError: If not connected or Redis returns an error.
            SerializationError: If data cannot be serialized.
        """
        if self._redis is None:
            raise PublisherError("FeedPublisher is not connected — call connect() first")

        payload = serialize(channel, data)
        try:
            deliveries: int = await self._redis.publish(channel, payload)
        except RedisError as exc:
            raise PublisherError(f"Redis publish failed on channel '{channel}'") from exc

        logger.debug("Published to '%s', reached %d subscriber(s)", channel, deliveries)
        return deliveries

    async def publish_many(self, channels: list[str], data: dict[str, Any]) -> int:
        """
        Publish the same data dict to multiple channels.

        Args:
            channels: List of Redis channel names.
            data:     JSON-serializable dict payload.

        Returns:
            Total subscriber delivery count summed across all channels.

        Raises:
            PublisherError: If not connected or any Redis publish fails.
            SerializationError: If data cannot be serialized.
        """
        if self._redis is None:
            raise PublisherError("FeedPublisher is not connected — call connect() first")

        total = 0
        for channel in channels:
            total += await self.publish(channel, data)

        logger.debug(
            "Published to %d channel(s), reached %d subscriber(s) total",
            len(channels),
            total,
        )
        return total
