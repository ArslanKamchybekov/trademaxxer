"""
news_streamer.pubsub — News-specific pub/sub integration.

Public API:
    NewsPublisher  — publishes TaggedNewsItems to Redis feeds
    PublisherError — raised when publishing fails
    channels       — channel name constants and channels_for_item()
    serializer     — tagged_item_to_dict()
"""
from .publisher import NewsPublisher, PublisherError
from . import channels, serializer

__all__ = [
    "NewsPublisher",
    "PublisherError",
    "channels",
    "serializer",
]
