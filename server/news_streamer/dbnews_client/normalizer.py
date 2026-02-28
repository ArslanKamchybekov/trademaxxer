"""
DBNews Data Normalizer

Transforms raw DBNews WebSocket messages into internal RawNewsItem format.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import json

from news_streamer.core.types import ValidationError
from news_streamer.models.news import RawNewsItem, SourceType, Urgency

logger = logging.getLogger(__name__)

# Maximum headline length before truncation
MAX_HEADLINE_LENGTH = 280

# Sentence boundary pattern for headline extraction
SENTENCE_END_PATTERN = re.compile(r'[.!?]\s+')


def _convert_to_string(item: Any) -> str:
    """
    Convert item to string for ClickHouse storage.

    DBNews coinReasons can be dicts, strings, or other types.
    """
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        # Try to extract a meaningful string, otherwise JSON serialize
        if "reason" in item:
            return str(item["reason"])
        return json.dumps(item)
    return str(item)


def parse_timestamp(ts: str) -> datetime:
    """
    Parse ISO 8601 timestamp to UTC datetime.

    Args:
        ts: Timestamp string in format "2025-07-24T17:06:15.272Z"

    Returns:
        Timezone-aware datetime in UTC

    Raises:
        ValidationError: If timestamp format is invalid
    """
    if not ts:
        raise ValidationError("Timestamp is empty", field="ts")

    try:
        # Handle 'Z' suffix (Zulu time = UTC)
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"

        dt = datetime.fromisoformat(ts)

        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except ValueError as e:
        raise ValidationError(
            f"Invalid timestamp format: {ts}",
            field="ts",
            value=ts,
        ) from e


def extract_headline(text: str) -> str:
    """
    Extract headline from full text.

    Rules:
    - If text <= MAX_HEADLINE_LENGTH chars: use full text
    - Otherwise: extract first sentence
    - Fallback: first MAX_HEADLINE_LENGTH chars + "..."

    Args:
        text: Full text content

    Returns:
        Extracted headline
    """
    if not text:
        return ""

    text = text.strip()

    # If short enough, use full text
    if len(text) <= MAX_HEADLINE_LENGTH:
        return text

    # Try to find first sentence
    match = SENTENCE_END_PATTERN.search(text)
    if match:
        first_sentence = text[:match.end()].strip()
        if len(first_sentence) <= MAX_HEADLINE_LENGTH:
            return first_sentence

    # Fallback: truncate with ellipsis
    return text[:MAX_HEADLINE_LENGTH - 3].strip() + "..."


def determine_urgency(raw: dict[str, Any]) -> Urgency:
    """
    Determine urgency level from DBNews fields.

    Args:
        raw: Raw DBNews message

    Returns:
        Urgency level
    """
    tags = raw.get("tags", [])
    is_highlight = raw.get("isHighlight", False)

    # HOT tag = breaking news
    if "HOT" in tags:
        return Urgency.BREAKING

    # isHighlight = high priority
    if is_highlight:
        return Urgency.HIGH

    # WARM tag = elevated but not breaking
    if "WARM" in tags:
        return Urgency.HIGH

    return Urgency.NORMAL


def get_source_handle(raw: dict[str, Any]) -> str:
    """
    Extract source handle based on news type.

    Args:
        raw: Raw DBNews message

    Returns:
        Source handle (Twitter handle, Telegram ID, etc.)
    """
    news_type = raw.get("newsType", "").lower()

    if news_type == "twitter":
        return raw.get("tweeterHandle", "")
    if news_type == "telegram":
        return raw.get("telegramId", "")

    return ""


def validate_dbnews_message(raw: dict[str, Any]) -> None:
    """
    Validate raw DBNews message structure.

    Args:
        raw: Raw message from DBNews

    Raises:
        ValidationError: If required fields are missing or invalid
    """
    if not isinstance(raw, dict):
        raise ValidationError(
            f"Expected dict, got {type(raw).__name__}",
            field="message",
            value=raw,
        )

    # Required: _id
    if not raw.get("_id"):
        raise ValidationError(
            "Missing required field: _id",
            field="_id",
        )

    # Required: text (content)
    text = raw.get("text", "")
    if not text or not text.strip():
        raise ValidationError(
            "Missing or empty required field: text",
            field="text",
        )

    # Required: ts (timestamp)
    if not raw.get("ts"):
        raise ValidationError(
            "Missing required field: ts",
            field="ts",
        )


def normalize_news(raw: dict[str, Any]) -> RawNewsItem:
    """
    Transform single DBNews message to RawNewsItem.

    Args:
        raw: Raw message from DBNews WebSocket

    Returns:
        Normalized RawNewsItem

    Raises:
        ValidationError: If message is invalid
    """
    # Validate first
    validate_dbnews_message(raw)

    # Parse timestamp
    timestamp = parse_timestamp(raw["ts"])

    # Extract text content
    text = raw.get("text", "").strip()
    headline = extract_headline(text)

    # Determine source type
    news_type = raw.get("newsType", "Other")
    source_type = SourceType.from_string(news_type)

    # Extract arrays, ensuring they're tuples
    coins = raw.get("coins", [])
    coin_reasons = raw.get("coinReasons", [])
    filter_reasons = raw.get("filterReasons", [])
    highlighted_words = raw.get("highlightedWords", [])
    tags = raw.get("tags", [])

    return RawNewsItem(
        id=raw["_id"],
        timestamp=timestamp,
        headline=headline,
        body=text,
        source_type=source_type,
        source_handle=get_source_handle(raw),
        source_description=raw.get("description", ""),
        source_url=raw.get("link", ""),
        source_avatar=raw.get("avatarLink", ""),
        media_url=raw.get("img", ""),
        pre_tagged_tickers=tuple(coins) if isinstance(coins, list) else (),
        ticker_reasons=tuple(_convert_to_string(r) for r in coin_reasons) if isinstance(coin_reasons, list) else (),
        pre_tagged_categories=tuple(filter_reasons) if isinstance(filter_reasons, list) else (),
        pre_highlighted_keywords=tuple(highlighted_words) if isinstance(highlighted_words, list) else (),
        is_priority=bool(raw.get("isHighlight", False)),
        is_narrative=bool(raw.get("isNarrative", False)),
        urgency_tags=tuple(tags) if isinstance(tags, list) else (),
        economic_event_type=raw.get("eeType", ""),
        raw_data=raw,
    )


