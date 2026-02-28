"""
pub_sub_feed — Generic Redis-backed pub/sub primitives.

Public API:
    FeedPublisher  — publish dicts to named Redis channels
    FeedSubscriber — subscribe to channels and pull items one at a time
    serialize      — encode (channel, dict) -> JSON string
    deserialize    — decode JSON string -> (channel, dict)
"""
from .publisher import FeedPublisher, PublisherError
from .subscriber import FeedSubscriber, SubscriberError
from .serializer import SerializationError, serialize, deserialize

__all__ = [
    "FeedPublisher",
    "PublisherError",
    "FeedSubscriber",
    "SubscriberError",
    "SerializationError",
    "serialize",
    "deserialize",
]
