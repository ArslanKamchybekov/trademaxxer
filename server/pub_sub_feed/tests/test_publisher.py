"""
Tests for pub_sub_feed.publisher

All Redis I/O is replaced with AsyncMock — no live Redis required.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from pub_sub_feed.publisher import FeedPublisher, PublisherError
from pub_sub_feed.serializer import SerializationError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """
    Patch pub_sub_feed.publisher.Redis so that Redis.from_url() returns
    an AsyncMock instance. Yields the mock Redis instance.
    """
    with patch("pub_sub_feed.publisher.Redis") as mock_cls:
        instance = AsyncMock()
        instance.ping = AsyncMock(return_value=True)
        instance.publish = AsyncMock(return_value=1)
        mock_cls.from_url.return_value = instance
        yield instance


@pytest.fixture
async def connected_publisher(mock_redis):
    """A FeedPublisher that has already called connect()."""
    publisher = FeedPublisher(redis_url="redis://localhost:6379/0")
    await publisher.connect()
    yield publisher
    await publisher.close()


# ── connect() ────────────────────────────────────────────────────────────────

async def test_connect_calls_ping(mock_redis):
    publisher = FeedPublisher(redis_url="redis://localhost:6379/0")
    await publisher.connect()
    mock_redis.ping.assert_called_once()
    await publisher.close()


async def test_connect_ping_failure_raises_publisher_error(mock_redis):
    mock_redis.ping.side_effect = RedisError("connection refused")

    publisher = FeedPublisher(redis_url="redis://localhost:6379/0")
    with pytest.raises(PublisherError, match="Cannot connect"):
        await publisher.connect()


# ── publish() ─────────────────────────────────────────────────────────────────

async def test_publish_before_connect_raises():
    publisher = FeedPublisher(redis_url="redis://localhost:6379/0")
    with pytest.raises(PublisherError, match="not connected"):
        await publisher.publish("news:all", {"key": "value"})


async def test_publish_calls_redis_publish_with_correct_args(connected_publisher, mock_redis):
    channel = "news:all"
    data = {"id": "x1", "headline": "Breaking"}

    await connected_publisher.publish(channel, data)

    mock_redis.publish.assert_called_once()
    call_channel, call_payload = mock_redis.publish.call_args.args

    assert call_channel == channel
    # payload must be a valid JSON envelope
    envelope = json.loads(call_payload)
    assert envelope["channel"] == channel
    assert envelope["data"] == data


async def test_publish_returns_delivery_count(connected_publisher, mock_redis):
    mock_redis.publish.return_value = 5

    count = await connected_publisher.publish("news:all", {"id": "x2"})

    assert count == 5


async def test_publish_redis_error_raises_publisher_error(connected_publisher, mock_redis):
    mock_redis.publish.side_effect = RedisError("timeout")

    with pytest.raises(PublisherError, match="Redis publish failed"):
        await connected_publisher.publish("news:all", {"id": "x3"})


# ── publish_many() ────────────────────────────────────────────────────────────

async def test_publish_many_before_connect_raises():
    publisher = FeedPublisher(redis_url="redis://localhost:6379/0")
    with pytest.raises(PublisherError, match="not connected"):
        await publisher.publish_many(["news:all"], {"key": "value"})


async def test_publish_many_sums_deliveries(connected_publisher, mock_redis):
    mock_redis.publish.return_value = 2
    channels = ["news:all", "news:urgency:breaking", "news:category:crypto"]

    total = await connected_publisher.publish_many(channels, {"id": "x4"})

    assert total == 6  # 3 channels × 2 deliveries each
    assert mock_redis.publish.call_count == 3


async def test_publish_many_empty_channels_returns_zero(connected_publisher, mock_redis):
    total = await connected_publisher.publish_many([], {"id": "x5"})
    assert total == 0
    mock_redis.publish.assert_not_called()


# ── context manager ───────────────────────────────────────────────────────────

async def test_context_manager_connects_and_closes(mock_redis):
    async with FeedPublisher(redis_url="redis://localhost:6379/0") as pub:
        assert pub._redis is not None
        mock_redis.ping.assert_called_once()

    mock_redis.aclose.assert_called_once()
