"""
News Tagger Engine

Main orchestrator for news tagging pipeline.
Leverages DBNews pre-tagged data (coins, filterReasons, tags) as hints
while applying our own analysis for consistency and enhancement.

Also matches news against market names in ClickHouse to assign platform tags.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from ..lib.sentiment_analyzer import get_analyzer
from ..models.news import (
    Category,
    RawNewsItem,
    Sentiment,
    TaggedNewsItem,
    Urgency,
)

if TYPE_CHECKING:
    from ..config import TaggerConfig
    from ..platform_tags import PlatformTagLoader

logger = logging.getLogger(__name__)


class TaggingError(Exception):
    """Raised when tagging fails critically."""

    pass


@dataclass
class TaggerStats:
    """Statistics for the tagger."""

    items_tagged: int = 0
    items_failed: int = 0
    dbnews_hints_used: int = 0
    platform_tags_matched: int = 0


class NewsTagger:
    """
    News tagging orchestrator.

    Transforms RawNewsItem into TaggedNewsItem by:
    1. Extracting tickers (using DBNews coins as base)
    2. Classifying categories (using DBNews filterReasons as hints)
    3. Analyzing sentiment (VADER + financial domain knowledge)
    4. Extracting keywords (using DBNews highlightedWords)
    5. Determining urgency (from DBNews tags)
    6. Matching platform tags (from market_platform_tags in ClickHouse)
    """

    def __init__(
        self,
        config: TaggerConfig,
        platform_tag_loader: Optional[PlatformTagLoader] = None,
    ) -> None:
        self._config = config
        self._platform_tag_loader = platform_tag_loader
        self._stats = TaggerStats()

        # Initialize financial sentiment analyzer (VADER + financial domain)
        self._sentiment_analyzer = get_analyzer()

        logger.info(
            "NewsTagger initialized",
            extra={
                "use_dbnews_hints": config.use_dbnews_hints,
                "platform_tags_enabled": platform_tag_loader is not None,
                "sentiment_analyzer": "FinancialSentimentAnalyzer",
            },
        )

    @property
    def stats(self) -> TaggerStats:
        """Get tagger statistics."""
        return self._stats

    def tag(self, news: RawNewsItem) -> TaggedNewsItem:
        """
        Run full tagging pipeline on news item.

        Uses DBNews pre-tagged data as hints when available.
        """
        try:
            # Extract tickers
            tickers = self._extract_tickers(news)

            # Classify categories
            categories = self._classify_categories(news)

            # Analyze sentiment
            sentiment, sentiment_score = self._analyze_sentiment(news)

            # Extract keywords
            keywords = self._extract_keywords(news)

            # Determine urgency
            urgency = self._determine_urgency(news)

            # Match platform tags
            platform_tag_ids, platform_tag_slugs = self._match_platform_tags(news)

            tagged = TaggedNewsItem(
                id=news.id,
                timestamp=news.timestamp,
                received_at=datetime.now(timezone.utc),
                headline=news.headline,
                body=news.body,
                source_type=news.source_type,
                source_handle=news.source_handle,
                source_url=news.source_url,
                source_description=news.source_description,
                source_avatar=news.source_avatar,
                media_url=news.media_url,
                tickers=tickers,
                ticker_reasons=news.ticker_reasons,
                categories=categories,
                keywords=keywords,
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                urgency=urgency,
                urgency_tags=news.urgency_tags,
                is_highlight=news.is_priority,
                is_narrative=news.is_narrative,
                economic_event_type=news.economic_event_type,
                platform_tag_ids=platform_tag_ids,
                platform_tag_slugs=platform_tag_slugs,
                raw_data=news.raw_data,
            )

            self._stats.items_tagged += 1
            return tagged

        except Exception as e:
            self._stats.items_failed += 1
            logger.error(
                f"Tagging failed for news {news.id}: {e}",
                extra={"news_id": news.id, "error": str(e)},
            )
            raise TaggingError(f"Failed to tag news {news.id}") from e

    def _extract_tickers(self, news: RawNewsItem) -> tuple[str, ...]:
        """Extract tickers from news."""
        tickers: set[str] = set()

        # Use DBNews pre-tagged tickers as base
        if self._config.use_dbnews_hints and news.pre_tagged_tickers:
            tickers.update(news.pre_tagged_tickers)
            self._stats.dbnews_hints_used += 1

        # Could add additional extraction here

        # Sort and limit
        sorted_tickers = sorted(tickers)
        if len(sorted_tickers) > 20:
            logger.warning(
                f"Truncating {len(sorted_tickers)} tickers to 20",
                extra={"news_id": news.id},
            )
            sorted_tickers = sorted_tickers[:20]

        return tuple(sorted_tickers)

    _CRYPTO_TICKERS = frozenset({
        "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "AVAX",
        "LINK", "MATIC", "UNI", "ATOM", "LTC", "BCH", "XLM",
    })

    def _classify_categories(self, news: RawNewsItem) -> tuple[Category, ...]:
        """Classify news into Kalshi-aligned categories."""
        categories: set[Category] = set()

        if self._config.use_dbnews_hints and news.pre_tagged_categories:
            for cat_str in news.pre_tagged_categories:
                cat = Category.from_string(cat_str)
                if cat:
                    categories.add(cat)

        if news.economic_event_type:
            categories.add(Category.ECONOMICS)

        if not categories:
            categories |= self._classify_from_text(news.headline)

        if not categories and news.pre_tagged_tickers:
            if any(t.upper() in self._CRYPTO_TICKERS for t in news.pre_tagged_tickers):
                categories.add(Category.CRYPTO)

        return tuple(sorted(categories, key=lambda c: c.value))

    @staticmethod
    def _classify_from_text(text: str) -> set[Category]:
        """Keyword fallback when DBNews hints are absent."""
        t = text.lower()
        cats: set[Category] = set()

        if any(w in t for w in [
            "election", "president", "congress", "senate", "trump", "biden",
            "sanctions", "war", "military", "nato", "ceasefire",
        ]):
            cats.add(Category.POLITICS)
        if any(w in t for w in [
            "fed ", "inflation", "cpi", "gdp", "unemployment", "rate cut",
            "rate hike", "fomc", "recession", "tariff", "jobs report",
        ]):
            cats.add(Category.ECONOMICS)
        if any(w in t for w in [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "solana",
            "stablecoin", "defi",
        ]):
            cats.add(Category.CRYPTO)
        if any(w in t for w in [
            "s&p", "dow", "nasdaq", "earnings", "stock", "bond", "yield",
            "oil", "gold", "crude",
        ]):
            cats.add(Category.FINANCIALS)
        if any(w in t for w in [
            "apple", "google", "microsoft", "amazon", "tesla", "nvidia",
            "meta", "openai",
        ]):
            cats.add(Category.COMPANIES)
        if any(w in t for w in [
            " ai ", "artificial intelligence", "quantum", "semiconductor",
            "fda", "vaccine", "launch",
        ]):
            cats.add(Category.TECH_SCIENCE)
        if any(w in t for w in [
            "climate", "hurricane", "wildfire", "emission", "drought",
        ]):
            cats.add(Category.CLIMATE)

        return cats

    def _analyze_sentiment(self, news: RawNewsItem) -> tuple[Sentiment, float]:
        """
        Analyze sentiment of news using VADER + financial domain knowledge.

        Uses FinancialSentimentAnalyzer which combines:
        - VADER base sentiment analysis
        - Financial phrase detection (rate cuts, earnings beat, etc.)
        - Economic indicator patterns (CPI, GDP, unemployment)
        """
        # Combine headline and body for analysis
        text = news.headline
        if news.body:
            text = f"{text} {news.body}"

        # Get sentiment from financial analyzer
        result = self._sentiment_analyzer.analyze(text)

        # Map string sentiment to enum
        sentiment_str = result["sentiment"]
        if sentiment_str == "bullish":
            sentiment = Sentiment.BULLISH
        elif sentiment_str == "bearish":
            sentiment = Sentiment.BEARISH
        else:
            sentiment = Sentiment.NEUTRAL

        score = result["score"]

        # Log matched signals for debugging (only if there are any)
        if result.get("matched_signals"):
            logger.debug(
                f"Sentiment analysis for {news.id}: {sentiment_str} ({score:.3f})",
                extra={
                    "news_id": news.id,
                    "sentiment": sentiment_str,
                    "score": score,
                    "matched_signals": result["matched_signals"],
                    "processing_time_ms": result["processing_time_ms"],
                },
            )

        return sentiment, score

    def _extract_keywords(self, news: RawNewsItem) -> tuple[str, ...]:
        """Extract keywords from news."""
        keywords: set[str] = set()

        # Use DBNews highlighted words as base
        if self._config.use_dbnews_hints and news.pre_highlighted_keywords:
            keywords.update(news.pre_highlighted_keywords)

        # Could add additional keyword extraction here

        # Limit keywords
        sorted_keywords = sorted(keywords)[:10]
        return tuple(sorted_keywords)

    def _determine_urgency(self, news: RawNewsItem) -> Urgency:
        """Determine urgency level from DBNews tags."""
        if "HOT" in news.urgency_tags:
            return Urgency.BREAKING
        if news.is_priority:
            return Urgency.HIGH
        if news.is_narrative:
            return Urgency.NORMAL

        return Urgency.NORMAL

    def _match_platform_tags(
        self, news: RawNewsItem
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """
        Match news against TagRules to get platform tags.

        Returns:
            Tuple of (tag_ids, tag_slugs)
        """
        if not self._platform_tag_loader:
            return (), ()

        try:
            matched_tags = self._platform_tag_loader.evaluate_news(
                headline=news.headline,
                body=news.body,
            )

            if matched_tags:
                self._stats.platform_tags_matched += 1
                tag_ids = tuple(str(tag.id) for tag in matched_tags)
                tag_slugs = tuple(tag.slug for tag in matched_tags)
                logger.debug(
                    f"Matched {len(tag_ids)} platform tags for news",
                    extra={"news_id": news.id, "tag_slugs": tag_slugs},
                )
                return tag_ids, tag_slugs

            return (), ()

        except Exception as e:
            logger.warning(
                f"Platform tag matching failed: {e}",
                extra={"news_id": news.id},
            )
            return (), ()
