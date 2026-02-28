"""
Agent Listener

Thin per-market wrapper that subscribes to the Redis pub/sub channels
matching its market's tags via FeedSubscriber, and calls Modal when
a story arrives. One listener per market — no centralised dispatcher.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from pub_sub_feed import FeedSubscriber
from news_streamer.pubsub.channels import ALL, CATEGORY_PREFIX

from agents.schemas import Decision, MarketConfig, StoryPayload

logger = logging.getLogger(__name__)


@dataclass
class ListenerStats:
    stories_received: int = 0
    decisions_yes: int = 0
    decisions_no: int = 0
    decisions_skip: int = 0
    errors: int = 0


def _wire_to_story(data: dict[str, Any]) -> StoryPayload:
    """Convert the camelCase pubsub wire dict to a StoryPayload."""
    return StoryPayload(
        id=data["id"],
        headline=data["headline"],
        body=data.get("body", ""),
        tags=tuple(data.get("categories", ())),
        source=data.get("sourceHandle", ""),
        timestamp=datetime.fromisoformat(data["timestamp"]),
    )


class AgentListener:
    """
    Subscribes to the Redis pub/sub channels for a single market and
    calls Modal on every matching story.

    One instance per market. The runner spawns all of them as concurrent tasks.
    """

    def __init__(
        self,
        market: MarketConfig,
        redis_url: str,
        evaluate_fn: Callable[
            [StoryPayload, MarketConfig], Awaitable[Decision]
        ] | None = None,
        on_decision: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._market = market
        self._redis_url = redis_url
        self._evaluate_fn = evaluate_fn or _modal_evaluate
        self._on_decision = on_decision
        self._stats = ListenerStats()

    @property
    def market(self) -> MarketConfig:
        return self._market

    @property
    def stats(self) -> ListenerStats:
        return self._stats

    def _feeds(self) -> list[str]:
        """Map market tags to Redis channel names, plus news:all as fallback."""
        feeds = [ALL]
        for tag in self._market.tags:
            ch = f"{CATEGORY_PREFIX}{tag}"
            if ch not in feeds:
                feeds.append(ch)
        return feeds

    async def run(self) -> None:
        """Subscribe to this market's tag channels. Blocks until cancelled."""
        feeds = self._feeds()
        logger.info(
            f"Agent for {self._market.address[:16]}… subscribing to {feeds} "
            f"| {self._market.question[:60]}"
        )

        seen: set[str] = set()
        async with FeedSubscriber(feeds=feeds, redis_url=self._redis_url) as sub:
            while True:
                result = await sub.pull(timeout=1.0)
                if result is None:
                    continue
                channel, data = result
                story_id = data.get("id", "")
                if story_id in seen:
                    continue
                seen.add(story_id)
                if len(seen) > 500:
                    seen.clear()
                await self._on_story(channel, data)

    async def _on_story(self, channel: str, data: dict[str, Any]) -> None:
        """Handle a story that arrived on one of our subscribed channels."""
        self._stats.stories_received += 1

        try:
            story = _wire_to_story(data)
        except (KeyError, ValueError) as e:
            logger.warning(f"Malformed story on {channel}: {e}")
            self._stats.errors += 1
            return

        try:
            decision = await self._evaluate_fn(story, self._market)
        except Exception as e:
            self._stats.errors += 1
            logger.error(
                f"Evaluation failed for {self._market.address[:16]}… "
                f"on story {story.id}: {e}"
            )
            return

        if decision.action == "SKIP":
            self._stats.decisions_skip += 1
        elif decision.action == "YES":
            self._stats.decisions_yes += 1
        else:
            self._stats.decisions_no += 1

        logger.info(
            f"[{decision.action}] {self._market.address[:16]}… "
            f"conf={decision.confidence:.2f} ({decision.latency_ms:.0f}ms) "
            f"| {story.headline[:60]}"
        )

        if self._on_decision:
            payload = decision.to_dict()
            payload["headline"] = story.headline
            payload["market_question"] = self._market.question
            try:
                await self._on_decision(payload)
            except Exception as e:
                logger.warning(f"on_decision callback failed: {e}")


async def _modal_evaluate(story: StoryPayload, market: MarketConfig) -> Decision:
    """
    Default evaluate_fn: calls the deployed MarketAgent (Groq) on Modal.
    """
    import modal

    Cls = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")
    agent = Cls()

    result = await agent.evaluate.remote.aio(story.to_dict(), market.to_dict())
    return Decision.from_dict(result)


async def run_all_listeners(
    markets: list[MarketConfig],
    redis_url: str,
    evaluate_fn: Callable[
        [StoryPayload, MarketConfig], Awaitable[Decision]
    ] | None = None,
    on_decision: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> list[asyncio.Task]:
    """
    Spawn one AgentListener per market as concurrent tasks.

    Returns the list of asyncio Tasks so the caller can cancel them on shutdown.
    """
    listeners = [
        AgentListener(market, redis_url, evaluate_fn, on_decision)
        for market in markets
    ]

    logger.info(f"Spawning {len(listeners)} agent listener(s)")

    tasks = [
        asyncio.create_task(listener.run(), name=f"agent-{listener.market.address[:12]}")
        for listener in listeners
    ]

    return tasks
