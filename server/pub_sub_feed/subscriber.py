"""
Feed Subscriber

Subscribes to one or more Redis pub/sub channels and exposes a simple
blocking pull() interface. Every subscriber independently receives every
message published to its subscribed channels — items are never consumed.

Usage:
    subscriber = FeedSubscriber(
        feeds=["news:all", "news:urgency:breaking"],
        redis_url="redis://localhost:6379/0",
    )
    await subscriber.connect()

    while True:
        result = await subscriber.pull()      # blocks until a message arrives
        if result is None:
            break                             # only when timeout is set
        channel, data = result
        print(channel, data)

    await subscriber.close()

Context manager usage:
    async with FeedSubscriber(feeds=[...], redis_url=...) as sub:
        channel, data = await sub.pull()
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from .serializer import SerializationError, deserialize

logger = logging.getLogger(__name__)


class SubscriberError(Exception):
    """Raised when a subscriber operation fails."""


class FeedSubscriber:
    """
    Subscribes to one or more named feeds and delivers messages via pull().

    Fan-out guarantee: Redis pub/sub sends every published message to every
    active subscriber independently — this subscriber never "consumes" a
    message from the channel.

    Args:
        feeds:     List of channel names to subscribe to (e.g. ["news:all"]).
        redis_url: Redis connection URL (e.g. "redis://localhost:6379/0").
    """

    def __init__(self, feeds: list[str], redis_url: str) -> None:
        if not feeds:
            raise ValueError("feeds must be a non-empty list of channel names")
        self._feeds = list(feeds)
        self._redis_url = redis_url
        self._redis: Redis | None = None
        self._pubsub: PubSub | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the Redis connection and subscribe to all configured feeds."""
        self._redis = Redis.from_url(self._redis_url, decode_responses=False)
        try:
            await self._redis.ping()
        except RedisError as exc:
            raise SubscriberError(f"Cannot connect to Redis: {exc}") from exc

        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        await self._pubsub.subscribe(*self._feeds)
        logger.info(
            "FeedSubscriber subscribed to %d feed(s): %s",
            len(self._feeds),
            self._feeds,
        )

    async def close(self) -> None:
        """Unsubscribe and close the Redis connection."""
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        logger.info("FeedSubscriber disconnected from Redis")

    # ── Context manager support ───────────────────────────────────────────────

    async def __aenter__(self) -> FeedSubscriber:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ── Main interface ────────────────────────────────────────────────────────

    async def pull(
        self,
        timeout: float | None = None,
    ) -> tuple[str, dict[str, Any]] | None:
        """
        Block until any subscribed feed delivers a new message.

        Args:
            timeout: Seconds to wait before returning None.
                     Pass None (default) to block indefinitely.

        Returns:
            (channel, data) where channel is the feed name and data is the
            deserialized news item dict, or None if timeout expires.

        Raises:
            SubscriberError: If not connected or the Redis connection breaks.
            SerializationError: If a received message cannot be decoded.
        """
        if self._pubsub is None:
            raise SubscriberError("FeedSubscriber is not connected — call connect() first")

        deadline = asyncio.get_event_loop().time() + timeout if timeout is not None else None

        while True:
            remaining: float | None = None
            if deadline is not None:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None

            try:
                # get_message with a short poll interval so we can honour timeout
                poll_timeout = min(remaining, 0.1) if remaining is not None else 0.1
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=poll_timeout,
                )
            except RedisError as exc:
                raise SubscriberError(f"Redis error while waiting for message: {exc}") from exc

            if message is None:
                # No message yet — loop and check timeout
                if deadline is not None and asyncio.get_event_loop().time() >= deadline:
                    return None
                # Yield to the event loop briefly before polling again
                await asyncio.sleep(0)
                continue

            if message.get("type") != "message":
                continue

            raw = message.get("data")
            if raw is None:
                continue

            channel, data = deserialize(raw)
            return channel, data

    @property
    def feeds(self) -> list[str]:
        """The list of channel names this subscriber is listening to."""
        return list(self._feeds)
