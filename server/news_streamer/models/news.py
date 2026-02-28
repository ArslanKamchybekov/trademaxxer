"""
News Data Models

Core data structures for news items at different pipeline stages.
All models use frozen dataclasses with __post_init__ validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SourceType(str, Enum):
    """News source platform type."""

    TWITTER = "Twitter"
    TELEGRAM = "Telegram"
    RSS = "RSS"
    NEWS_WIRE = "News"
    OTHER = "Other"

    @classmethod
    def from_string(cls, value: str) -> "SourceType":
        """Convert string to SourceType, defaulting to OTHER."""
        for member in cls:
            if member.value.lower() == value.lower():
                return member
        return cls.OTHER


class Sentiment(str, Enum):
    """Sentiment classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Urgency(str, Enum):
    """News urgency level."""

    BREAKING = "breaking"  # HOT tag or critical news
    HIGH = "high"  # isHighlight from DBNews
    NORMAL = "normal"  # Default
    LOW = "low"  # Routine/delayed news


class Category(str, Enum):
    """News category classification — mirrors Kalshi event categories."""

    POLITICS = "politics"
    SPORTS = "sports"
    CULTURE = "culture"
    CRYPTO = "crypto"
    CLIMATE = "climate"
    ECONOMICS = "economics"
    MENTIONS = "mentions"
    COMPANIES = "companies"
    FINANCIALS = "financials"
    TECH_SCIENCE = "tech_science"

    @classmethod
    def from_string(cls, value: str) -> Optional["Category"]:
        """Convert string to Category, returning None if not found."""
        v = value.lower().replace(" & ", "_").replace(" ", "_")
        for member in cls:
            if member.value == v:
                return member
        _ALIASES = {
            "macro": cls.ECONOMICS,
            "economic_data": cls.ECONOMICS,
            "geopolitics": cls.POLITICS,
            "regulation": cls.POLITICS,
            "stocks": cls.FINANCIALS,
            "earnings": cls.FINANCIALS,
            "forex": cls.FINANCIALS,
            "commodities": cls.FINANCIALS,
            "tech": cls.TECH_SCIENCE,
            "science": cls.TECH_SCIENCE,
        }
        return _ALIASES.get(v)


@dataclass(frozen=True)
class RawNewsItem:
    """
    Raw news received from DBNews before tagging pipeline.

    This represents the normalized data from DBNews WebSocket,
    preserving all pre-tagged hints for the tagger to use.
    """

    # Core identifiers
    id: str
    timestamp: datetime

    # Content
    headline: str
    body: str

    # Source information
    source_type: SourceType
    source_handle: str
    source_description: str
    source_url: str
    source_avatar: str
    media_url: str

    # Pre-extracted by DBNews (use as hints for tagger)
    pre_tagged_tickers: tuple[str, ...]
    ticker_reasons: tuple[str, ...]
    pre_tagged_categories: tuple[str, ...]
    pre_highlighted_keywords: tuple[str, ...]

    # Priority/Classification from DBNews
    is_priority: bool
    is_narrative: bool
    urgency_tags: tuple[str, ...]
    economic_event_type: str

    # Original payload
    raw_data: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.id:
            raise ValueError("id must be non-empty string")
        if not self.headline:
            raise ValueError("headline must be non-empty string")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")


@dataclass(frozen=True)
class TaggedNewsItem:
    """
    Fully processed news with extracted metadata from our tagger.

    This is the final output after the tagging pipeline,
    ready for broadcasting to clients and storage in ClickHouse.
    """

    # Core identifiers
    id: str
    timestamp: datetime
    received_at: datetime

    # Content
    headline: str
    body: str

    # Source information
    source_type: SourceType
    source_handle: str
    source_url: str

    # Our tagger results (required fields)
    tickers: tuple[str, ...]
    categories: tuple[Category, ...]
    keywords: tuple[str, ...]
    sentiment: Sentiment
    sentiment_score: float
    urgency: Urgency

    # Optional fields with defaults
    source_description: str = ""
    source_avatar: str = ""
    media_url: str = ""
    ticker_reasons: tuple[str, ...] = ()
    urgency_tags: tuple[str, ...] = ()
    is_highlight: bool = False
    is_narrative: bool = False
    economic_event_type: str = ""

    # Platform tags (matched from TagRules)
    platform_tag_ids: tuple[str, ...] = ()
    platform_tag_slugs: tuple[str, ...] = ()

    # Original payload
    raw_data: dict[str, Any] = None  # type: ignore

    def __post_init__(self) -> None:
        """Validate fields."""
        if not self.id:
            raise ValueError("id must be non-empty string")
        if not (-1.0 <= self.sentiment_score <= 1.0):
            raise ValueError(
                f"sentiment_score must be in range [-1.0, 1.0], got {self.sentiment_score}"
            )
