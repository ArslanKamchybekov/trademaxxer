"""
News Item Serializer

Converts a TaggedNewsItem into the plain dict that FeedPublisher publishes
to Redis. The wire format deliberately mirrors the WebSocket payload so
downstream consumers see the same field names regardless of transport.
"""
from __future__ import annotations

from typing import Any

from ..models.news import TaggedNewsItem


def tagged_item_to_dict(item: TaggedNewsItem) -> dict[str, Any]:
    """
    Serialize a TaggedNewsItem to a JSON-serializable dict.

    Field names use camelCase to match the existing WebSocket wire format.
    """
    return {
        "id": item.id,
        "timestamp": item.timestamp.isoformat(),
        "receivedAt": item.received_at.isoformat(),
        "headline": item.headline,
        "body": item.body,
        "sourceType": item.source_type.value,
        "sourceHandle": item.source_handle,
        "sourceUrl": item.source_url,
        "sourceDescription": item.source_description,
        "sourceAvatar": item.source_avatar,
        "mediaUrl": item.media_url,
        "tickers": list(item.tickers),
        "tickerReasons": list(item.ticker_reasons),
        "categories": [c.value for c in item.categories],
        "highlightedWords": list(item.keywords),
        "sentiment": item.sentiment.value,
        "sentimentScore": item.sentiment_score,
        "urgency": item.urgency.value,
        "urgencyTags": list(item.urgency_tags),
        "isHighlight": item.is_highlight,
        "isNarrative": item.is_narrative,
        "economicEventType": item.economic_event_type,
        "platformTagIds": list(item.platform_tag_ids),
        "platformTags": list(item.platform_tag_slugs),
    }
