"""
News Feed Channel Definitions

Maps TaggedNewsItem fields to Redis channel names and provides the
channels_for_item() helper used by NewsPublisher.

Channel naming scheme:
  news:all                    — every tagged item
  news:urgency:{level}        — e.g. news:urgency:breaking
  news:category:{category}    — e.g. news:category:crypto
  news:ticker:{TICKER}        — e.g. news:ticker:BTC
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.news import TaggedNewsItem

# ── Well-known channel names ──────────────────────────────────────────────────

ALL = "news:all"

URGENCY_BREAKING = "news:urgency:breaking"
URGENCY_HIGH = "news:urgency:high"
URGENCY_NORMAL = "news:urgency:normal"
URGENCY_LOW = "news:urgency:low"

CATEGORY_PREFIX = "news:category:"
TICKER_PREFIX = "news:ticker:"


# ── Per-item helpers ──────────────────────────────────────────────────────────

def urgency_channel(urgency: str) -> str:
    return f"news:urgency:{urgency}"


def category_channel(category: str) -> str:
    return f"{CATEGORY_PREFIX}{category}"


def ticker_channel(ticker: str) -> str:
    return f"{TICKER_PREFIX}{ticker.upper()}"


def channels_for_item(item: TaggedNewsItem) -> list[str]:
    """
    Return all channels a TaggedNewsItem should be published to.

    Always includes news:all. Also includes one urgency channel, one channel
    per category, and one channel per ticker.
    """
    result: list[str] = [ALL, urgency_channel(item.urgency.value)]

    for category in item.categories:
        result.append(category_channel(category.value))

    for ticker in item.tickers:
        result.append(ticker_channel(ticker))

    return result
