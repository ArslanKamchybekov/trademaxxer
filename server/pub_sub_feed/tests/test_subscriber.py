"""
Tests for pub_sub_feed.subscriber

All Redis I/O is replaced with AsyncMock — no live Redis required.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

from pub_sub_feed.serializer import serialize
from pub_sub_feed.subscriber import FeedSubscriber, SubscriberError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_message(channel: str, data: dict) -> dict:
    """Build a mock Redis pub/sub message dict."""
    return {
        "type": "message",
        "channel": channel.encode(),
        "data": serialize(channel, data).encode(),
    }


def _make_subscribe_confirmation(channel: str) -> dict:
    """Build a subscribe-confirmation message (type != 'message')."""
    return {
        "type": "subscribe",
        "channel": channel.encode(),
        "data": 1,
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis_and_pubsub():
    """
    Patch pub_sub_feed.subscriber.Redis so that:
      - Redis.from_url() returns a mock Redis instance
      - instance.pubsub() returns a mock PubSub handle
    Yields (mock_redis_instance, mock_pubsub).
    """
    with patch("pub_sub_feed.subscriber.Redis") as mock_cls:
        redis_instance = AsyncMock()
        redis_instance.ping = AsyncMock(return_value=True)

        pubsub = AsyncMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()
        pubsub.aclose = AsyncMock()
        pubsub.get_message = AsyncMock(return_value=None)

        # pubsub() is synchronous in the real client, returns the PubSub object
        redis_instance.pubsub = MagicMock(return_value=pubsub)

        mock_cls.from_url.return_value = redis_instance
        yield redis_instance, pubsub


@pytest.fixture
async def connected_subscriber(mock_redis_and_pubsub):
    """A FeedSubscriber subscribed to ['news:all'] that has called connect()."""
    sub = FeedSubscriber(feeds=["news:all"], redis_url="redis://localhost:6379/0")
    await sub.connect()
    yield sub
    await sub.close()


# ── Constructor ───────────────────────────────────────────────────────────────

def test_empty_feeds_raises_value_error():
    with pytest.raises(ValueError, match="non-empty"):
        FeedSubscriber(feeds=[], redis_url="redis://localhost:6379/0")


def test_feeds_property():
    feeds = ["news:all", "news:urgency:breaking"]
    sub = FeedSubscriber(feeds=feeds, redis_url="redis://localhost:6379/0")
    assert sub.feeds == feeds
    # Ensure the property returns a copy, not the internal list
    sub.feeds.append("mutated")
    assert sub.feeds == feeds


# ── connect() ─────────────────────────────────────────────────────────────────

async def test_connect_subscribes_to_all_feeds(mock_redis_and_pubsub):
    _, pubsub = mock_redis_and_pubsub
    feeds = ["news:all", "news:urgency:breaking"]
    sub = FeedSubscriber(feeds=feeds, redis_url="redis://localhost:6379/0")

    await sub.connect()

    pubsub.subscribe.assert_called_once_with(*feeds)
    await sub.close()


async def test_connect_ping_failure_raises_subscriber_error(mock_redis_and_pubsub):
    redis_instance, _ = mock_redis_and_pubsub
    redis_instance.ping.side_effect = RedisError("refused")

    sub = FeedSubscriber(feeds=["news:all"], redis_url="redis://localhost:6379/0")
    with pytest.raises(SubscriberError, match="Cannot connect"):
        await sub.connect()


# ── pull() ────────────────────────────────────────────────────────────────────

async def test_pull_before_connect_raises():
    sub = FeedSubscriber(feeds=["news:all"], redis_url="redis://localhost:6379/0")
    with pytest.raises(SubscriberError, match="not connected"):
        await sub.pull(timeout=0.01)


async def test_pull_returns_channel_and_data(connected_subscriber, mock_redis_and_pubsub):
    _, pubsub = mock_redis_and_pubsub
    channel = "news:all"
    data = {"id": "abc", "headline": "Test"}
    pubsub.get_message.return_value = _make_message(channel, data)

    result = await connected_subscriber.pull()

    assert result is not None
    returned_channel, returned_data = result
    assert returned_channel == channel
    assert returned_data == data


async def test_pull_skips_subscribe_confirmation_then_returns_message(
    connected_subscriber, mock_redis_and_pubsub
):
    """
    The first get_message() call returns a subscribe confirmation (type='subscribe');
    the second returns a real message. pull() must skip the confirmation.
    """
    _, pubsub = mock_redis_and_pubsub
    channel = "news:all"
    data = {"id": "xyz"}

    pubsub.get_message.side_effect = [
        _make_subscribe_confirmation(channel),
        _make_message(channel, data),
    ]

    returned_channel, returned_data = await connected_subscriber.pull()
    assert returned_channel == channel
    assert returned_data == data


async def test_pull_skips_message_with_none_data(connected_subscriber, mock_redis_and_pubsub):
    """
    A message whose 'data' field is None must be silently skipped.
    The next valid message is returned instead.
    """
    _, pubsub = mock_redis_and_pubsub
    channel = "news:all"
    real_data = {"id": "real"}

    pubsub.get_message.side_effect = [
        {"type": "message", "channel": channel.encode(), "data": None},
        _make_message(channel, real_data),
    ]

    returned_channel, returned_data = await connected_subscriber.pull()
    assert returned_channel == channel
    assert returned_data == real_data


async def test_pull_timeout_returns_none(connected_subscriber, mock_redis_and_pubsub):
    """When no message arrives within the timeout, pull() returns None."""
    _, pubsub = mock_redis_and_pubsub
    pubsub.get_message.return_value = None  # always empty

    result = await connected_subscriber.pull(timeout=0.05)

    assert result is None


async def test_pull_redis_error_raises_subscriber_error(connected_subscriber, mock_redis_and_pubsub):
    _, pubsub = mock_redis_and_pubsub
    pubsub.get_message.side_effect = RedisError("broken pipe")

    with pytest.raises(SubscriberError, match="Redis error"):
        await connected_subscriber.pull(timeout=1.0)


# ── Fan-out ───────────────────────────────────────────────────────────────────

async def test_fanout_two_subscribers_both_receive_message():
    """
    Two independent FeedSubscribers on the same channel must each receive
    the message (fan-out). This is verified by giving each its own mock
    pubsub with the same message pre-loaded.
    """
    channel = "news:all"
    data = {"id": "fanout-test", "headline": "Fan-out works"}
    message = _make_message(channel, data)

    def _make_sub_with_message(msg):
        with patch("pub_sub_feed.subscriber.Redis") as mock_cls:
            redis_instance = AsyncMock()
            redis_instance.ping = AsyncMock(return_value=True)

            pubsub = AsyncMock()
            pubsub.subscribe = AsyncMock()
            pubsub.unsubscribe = AsyncMock()
            pubsub.aclose = AsyncMock()
            pubsub.get_message = AsyncMock(return_value=msg)
            redis_instance.pubsub = MagicMock(return_value=pubsub)
            mock_cls.from_url.return_value = redis_instance

            sub = FeedSubscriber(feeds=[channel], redis_url="redis://localhost:6379/0")
            return sub, mock_cls

    # Build subscriber A
    with patch("pub_sub_feed.subscriber.Redis") as mock_cls_a:
        redis_a = AsyncMock()
        redis_a.ping = AsyncMock(return_value=True)
        pubsub_a = AsyncMock()
        pubsub_a.subscribe = AsyncMock()
        pubsub_a.unsubscribe = AsyncMock()
        pubsub_a.aclose = AsyncMock()
        pubsub_a.get_message = AsyncMock(return_value=message)
        redis_a.pubsub = MagicMock(return_value=pubsub_a)
        mock_cls_a.from_url.return_value = redis_a

        sub_a = FeedSubscriber(feeds=[channel], redis_url="redis://localhost:6379/0")
        await sub_a.connect()
        result_a = await sub_a.pull()
        await sub_a.close()

    # Build subscriber B (separate mock — independent connection)
    with patch("pub_sub_feed.subscriber.Redis") as mock_cls_b:
        redis_b = AsyncMock()
        redis_b.ping = AsyncMock(return_value=True)
        pubsub_b = AsyncMock()
        pubsub_b.subscribe = AsyncMock()
        pubsub_b.unsubscribe = AsyncMock()
        pubsub_b.aclose = AsyncMock()
        pubsub_b.get_message = AsyncMock(return_value=message)
        redis_b.pubsub = MagicMock(return_value=pubsub_b)
        mock_cls_b.from_url.return_value = redis_b

        sub_b = FeedSubscriber(feeds=[channel], redis_url="redis://localhost:6379/0")
        await sub_b.connect()
        result_b = await sub_b.pull()
        await sub_b.close()

    assert result_a is not None
    assert result_b is not None
    assert result_a == result_b == (channel, data)


# ── Context manager ───────────────────────────────────────────────────────────

async def test_context_manager_connects_and_closes(mock_redis_and_pubsub):
    redis_instance, pubsub = mock_redis_and_pubsub

    async with FeedSubscriber(
        feeds=["news:all"], redis_url="redis://localhost:6379/0"
    ) as sub:
        assert sub._pubsub is not None
        pubsub.subscribe.assert_called_once_with("news:all")

    pubsub.unsubscribe.assert_called_once()
    pubsub.aclose.assert_called_once()
    redis_instance.aclose.assert_called_once()
