"""
News Publisher

Domain-aware wrapper around FeedPublisher. Given a TaggedNewsItem it:
  1. Serializes the item to a dict (tagged_item_to_dict)
  2. Derives all relevant channels    (channels_for_item)
  3. Fans the payload out to Redis    (FeedPublisher.publish_many)

Usage:
    publisher = NewsPublisher(redis_url="redis://localhost:6379/0")
    await publisher.connect()
    await publisher.publish(tagged_item)
    await publisher.close()

Context manager usage:
    async with NewsPublisher(redis_url=...) as pub:
        await pub.publish(tagged_item)
"""
from __future__ import annotations

import logging

from pub_sub_feed import FeedPublisher, PublisherError  # re-export for callers

from ..models.news import TaggedNewsItem
from .channels import channels_for_item
from .serializer import tagged_item_to_dict

logger = logging.getLogger(__name__)

__all__ = ["NewsPublisher", "PublisherError"]


class NewsPublisher:
    """
    Publishes TaggedNewsItems to all relevant Redis pub/sub channels.

    Delegates connection management and Redis I/O to FeedPublisher.
    """

    def __init__(self, redis_url: str) -> None:
        self._publisher = FeedPublisher(redis_url)

    async def connect(self) -> None:
        """Open the Redis connection."""
        await self._publisher.connect()

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._publisher.close()

    async def __aenter__(self) -> NewsPublisher:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def publish(self, item: TaggedNewsItem) -> int:
        """
        Serialize and fan out a tagged news item to all relevant channels.

        Returns the total subscriber delivery count across all channels.
        """
        data = tagged_item_to_dict(item)
        channels = channels_for_item(item)
        total = await self._publisher.publish_many(channels, data)
        logger.debug(
            "NewsPublisher: item %s published to %d channel(s), %d delivery(s)",
            item.id,
            len(channels),
            total,
        )
        return total
