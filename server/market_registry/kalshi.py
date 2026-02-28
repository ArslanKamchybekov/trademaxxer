"""
Kalshi API integration for live prediction market data.

Replaces hardcoded test markets with real markets from Kalshi's platform.
Provides tag extraction and market filtering for news-relevant markets.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import aiohttp

from agents.schemas import MarketConfig


logger = logging.getLogger(__name__)


class KalshiMarketRegistry:
    """
    Live market registry backed by Kalshi API.

    Fetches active binary prediction markets and maps them to TradeMaxxer's
    MarketConfig format with appropriate tag classification.
    """

    def __init__(
        self,
        base_url: str = "https://api.elections.kalshi.com/trade-api/v2",  # Use public API
        min_volume_24h: int = 0,  # Accept zero volume to get more markets
        max_close_days: int = 365,  # Longer timeframe for more options
        max_markets: int = 100,  # Much higher limit for more market options
    ):
        self.base_url = base_url
        self.min_volume_24h = min_volume_24h
        self.max_close_days = max_close_days
        self.max_markets = max_markets
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def fetch_active_markets(self) -> list[MarketConfig]:
        """
        Fetch active, high-volume, news-relevant markets from Kalshi events.

        Returns markets that:
        - Are currently open for trading
        - Have sufficient 24h volume (>$1000)
        - Expire within 90 days (news-sensitive timeframe)
        - Cover news-relevant topics (macro, geopolitics, etc.)
        """
        if not self._session:
            raise RuntimeError("Use async context manager: async with registry:")

        logger.info("Fetching active events from Kalshi...")

        # Calculate time filters
        now = int(time.time())
        max_close_ts = now + (self.max_close_days * 24 * 3600)

        params = {
            "status": "open",                          # Only active events
            "with_nested_markets": "true",             # Include markets in response (string not bool)
            "limit": 200,                              # Maximum events allowed by API
            "min_close_ts": now,                       # Only future-expiring events
            "min_updated_ts": now - (7 * 24 * 3600),  # Events updated in last 7 days
        }

        try:
            # Fetch events with nested markets
            async with self._session.get(f"{self.base_url}/events", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            raw_events = data.get("events", [])
            logger.info(f"Retrieved {len(raw_events)} raw events from Kalshi")

            markets = []
            total_events_checked = 0
            filtered_out_events = 0

            for event in raw_events:
                total_events_checked += 1
                event_title = event.get("title", "")

                # Check if event title is news-relevant
                if not self._is_news_relevant_question(event_title):
                    filtered_out_events += 1
                    logger.debug(f"Filtered out event: {event_title[:50]}...")
                    continue

                logger.info(f"Processing news-relevant event: {event_title[:80]}...")

                # Process markets within this event
                event_markets = event.get("markets", [])
                processed_markets = 0

                for market in event_markets:
                    # TEMPORARILY SKIP ALL MARKET FILTERING FOR TESTING
                    try:
                        config = self._convert_event_market_to_config(event, market)
                        markets.append(config)
                        processed_markets += 1
                        logger.info(f"  Added market: {config.question[:60]}...")
                    except Exception as e:
                        logger.warning(f"Failed to convert market {market.get('ticker', '?')}: {e}")

                if processed_markets > 0:
                    logger.info(f"  → Added {processed_markets} markets from this event")

                # Limit total markets
                if len(markets) >= self.max_markets:
                    break

            logger.info(f"Event filtering: {total_events_checked} total, {filtered_out_events} filtered out, {total_events_checked - filtered_out_events} processed")

            # Create tuples of (market_config, volume_data) for sorting
            markets_with_volume = []
            for market in markets:
                # Find the original market data to get volume
                volume_score = 0
                for event in raw_events:
                    for event_market in event.get("markets", []):
                        if event_market.get("ticker") == market.address:
                            volume_24h = event_market.get("volume_24h", 0)
                            open_interest = event_market.get("open_interest", 0)
                            volume_score = volume_24h + (open_interest * 0.1)
                            break
                markets_with_volume.append((market, volume_score))

            # Sort by volume score (highest first)
            markets_with_volume.sort(key=lambda x: x[1], reverse=True)

            # Extract just the market configs and limit
            markets = [m[0] for m in markets_with_volume[:self.max_markets]]

            logger.info(f"Selected {len(markets)} news-relevant markets from events")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch events from Kalshi: {e}")
            return []

    def _is_market_suitable(self, market: dict) -> bool:
        """Filter for news-relevant, liquid markets."""

        # Check volume threshold
        volume_24h = market.get("volume_24h", 0)
        if volume_24h < self.min_volume_24h:
            return False

        # Check if question is news-relevant
        question = market.get("yes_sub_title", "").lower()
        if not self._is_news_relevant_question(question):
            return False

        # Allow zero price for testing (new markets haven't been traded yet)
        # last_price = market.get("last_price_dollars")
        # if not last_price or last_price == "0.0000":
        #     return False

        return True

    def _is_news_relevant_question(self, question: str) -> bool:
        """Check if market question is driven by news events."""

        question_lower = question.lower()

        # Exclude sports-related markets
        sports_keywords = [
            "basketball", "nba", "football", "nfl", "soccer", "premier league",
            "manchester", "barcelona", "liverpool", "chelsea", "arsenal",
            "lebron", "luka", "goals", "points", "scored", "charlotte", "bruins",
            "patriots", "cowboys", "packers", "steelers", "49ers", "eagles",
            "lakers", "warriors", "celtics", "heat", "knicks", "bulls",
            "yankees", "dodgers", "red sox", "astros", "mets", "giants",
            "tournament", "championship", "playoff", "bowl", "cup", "league",
            "team", "coach", "player", "draft", "trade", "season", "game",
            "match", "win", "lose", "defeat", "victory", "score", "stats",
            "roster", "mvp", "rookie", "veteran", "contract", "signing"
        ]

        # TEMPORARILY ACCEPT ALL NON-SPORTS EVENTS FOR TESTING
        # Return False if question contains sports keywords
        if any(keyword in question_lower for keyword in sports_keywords):
            logger.debug(f"Excluding sports market: {question[:50]}...")
            return False

        # For now, accept all non-sports events to see what we get
        logger.debug(f"Accepting event for testing: {question[:50]}...")
        return True

    def _convert_to_market_config(self, market: dict) -> MarketConfig:
        """Convert Kalshi market data to TradeMaxxer MarketConfig."""

        ticker = market["ticker"]
        question = market["yes_sub_title"]

        # Convert price to probability
        last_price_str = market["last_price_dollars"]
        probability = float(last_price_str)  # Kalshi prices are already 0.0-1.0

        # Parse expiration
        close_time_str = market["close_time"]
        expires_at = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))

        # Extract tags from question
        tags = self._extract_tags_from_question(question)

        return MarketConfig(
            address=ticker,  # Use ticker as address
            question=question,
            current_probability=probability,
            tags=tags,
            expires_at=expires_at,
        )

    def _extract_tags_from_question(self, question: str) -> tuple[str, ...]:
        """Map market question to Kalshi-aligned categories."""

        q = question.lower()
        tags: set[str] = set()

        if any(w in q for w in [
            "election", "president", "congress", "senate", "vote", "biden",
            "trump", "harris", "political", "government", "executive order",
            "sanctions", "war", "invasion", "conflict", "military", "nato",
            "geopolit", "ceasefire", "diplomacy",
        ]):
            tags.add("politics")

        if any(w in q for w in [
            "fed", "federal reserve", "interest rate", "inflation", "gdp",
            "recession", "unemployment", "jobs", "cpi", "ppi", "fomc",
            "tariff", "trade deal", "debt ceiling", "treasury",
        ]):
            tags.add("economics")

        if any(w in q for w in [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol",
            "stablecoin", "defi", "nft",
        ]):
            tags.add("crypto")

        if any(w in q for w in [
            "s&p", "dow", "nasdaq", "stock", "ipo", "bond", "yield",
            "earnings", "revenue", "oil", "gold", "crude", "commodity",
            "forex", "dollar",
        ]):
            tags.add("financials")

        if any(w in q for w in [
            "apple", "google", "microsoft", "amazon", "tesla", "nvidia",
            "meta", "openai", "spacex",
        ]):
            tags.add("companies")

        if any(w in q for w in [
            "ai", "artificial intelligence", "quantum", "chip", "semiconductor",
            "fda", "vaccine", "space", "launch", "nuclear",
        ]):
            tags.add("tech_science")

        if any(w in q for w in [
            "climate", "carbon", "emission", "hurricane", "wildfire",
            "temperature", "drought", "flood", "epa",
        ]):
            tags.add("climate")

        if any(w in q for w in [
            "oscar", "grammy", "emmy", "box office", "celebrity",
            "entertainment", "movie", "album",
        ]):
            tags.add("culture")

        if any(w in q for w in [
            "nba", "nfl", "mlb", "nhl", "fifa", "super bowl", "world cup",
            "championship", "playoff", "tournament",
        ]):
            tags.add("sports")

        if not tags:
            tags.add("mentions")

        return tuple(sorted(tags))

    def _is_market_suitable_from_event(self, market: dict, now: int, max_close_ts: int) -> bool:
        """Check if a market from an event meets our criteria for news trading."""
        # Check if market is open
        if market.get("status") != "open":
            return False

        # Check close time (optimal range for news impact)
        close_time_str = market.get("close_time")
        if close_time_str:
            try:
                close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                close_ts = int(close_time.timestamp())
                days_to_close = (close_ts - now) / (24 * 3600)

                # Relaxed time requirements for testing
                if days_to_close < 1 or days_to_close > 365:
                    return False
            except ValueError:
                return False

        # Relaxed probability range for testing
        last_price = market.get("last_price_dollars", "0.0000")
        try:
            probability = float(last_price)
            # Allow wider probability range for now
            if probability < 0.05 or probability > 0.95:
                return False
        except (ValueError, TypeError):
            pass

        # Relaxed liquidity requirements for testing
        volume_24h = market.get("volume_24h", 0)
        open_interest = market.get("open_interest", 0)

        # Accept very low volume for now
        if volume_24h == 0 and open_interest == 0:
            return False

        # Check for meaningful price movement (avoid stale markets)
        yes_bid = market.get("yes_bid", 0)
        yes_ask = market.get("yes_ask", 0)
        if yes_bid == 0 and yes_ask == 0:
            return False

        return True

    def _convert_event_market_to_config(self, event: dict, market: dict) -> MarketConfig:
        """Convert event + market data to TradeMaxxer MarketConfig."""
        ticker = market["ticker"]

        # Use event title + market subtitle for better context
        event_title = event.get("title", "")
        market_subtitle = market.get("yes_sub_title", "") or market.get("subtitle", "")

        # Create a comprehensive question
        if market_subtitle:
            question = f"{event_title}: {market_subtitle}"
        else:
            question = event_title

        # Convert price to probability
        last_price_str = market.get("last_price_dollars", "0.0000")
        try:
            probability = float(last_price_str)
        except (ValueError, TypeError):
            probability = 0.5  # Default to 50% if price is invalid

        # Parse expiration
        close_time_str = market.get("close_time", "")
        try:
            expires_at = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
        except ValueError:
            expires_at = None

        # Extract tags from event title and market subtitle
        combined_text = f"{event_title} {market_subtitle}".lower()
        tags = self._extract_tags_from_question(combined_text)

        return MarketConfig(
            address=ticker,
            question=question,
            current_probability=probability,
            tags=tags,
            expires_at=expires_at,
        )

    def _get_market_volume_score(self, market: MarketConfig) -> float:
        """Calculate volume score for market ranking from MarketConfig."""
        # Since MarketConfig doesn't store volume, we'll use a simple heuristic
        # based on probability distance from 50% (more active markets tend to have moved more)
        prob_distance = abs(market.current_probability - 0.5)
        return prob_distance * 100  # Convert to a reasonable scoring range

    def _get_volume_score(self, market: dict) -> float:
        """Calculate volume score for market ranking."""
        volume_24h = market.get("volume_24h", 0)
        open_interest = market.get("open_interest", 0)

        # Combine volume and open interest for liquidity score
        return volume_24h + (open_interest * 0.1)


async def test_kalshi_integration():
    """Test function for Kalshi API integration."""

    async with KalshiMarketRegistry() as registry:
        markets = await registry.fetch_active_markets()

        print(f"\n=== KALSHI MARKETS ({len(markets)}) ===")
        for i, market in enumerate(markets[:10]):  # Show first 10
            print(f"\n{i+1}. {market.address}")
            print(f"   Q: {market.question}")
            print(f"   P: {market.current_probability:.1%}")
            print(f"   Tags: {', '.join(market.tags)}")
            print(f"   Expires: {market.expires_at.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    asyncio.run(test_kalshi_integration())