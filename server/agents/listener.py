"""
Agent Listener

Thin per-market wrapper that subscribes to the Redis tag channels matching
its market's _tags, and calls Modal when a story arrives. One listener
per market — no centralised dispatcher.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agents.schemas import Decision, MarketConfig, StoryPayload
from stream.interface import StreamProducer, TaggedStreamConsumer

logger = logging.getLogger(__name__)

STREAM_DECISIONS = "decisions:raw"


@dataclass
class ListenerStats:
    stories_received: int = 0
    decisions_yes: int = 0
    decisions_no: int = 0
    decisions_skip: int = 0
    errors: int = 0


class AgentListener:
    """
    Subscribes to the tag channels for a single market and calls Modal
    on every matching story.

    One instance per market. The runner spawns all of them as concurrent tasks.
    """

    def __init__(
        self,
        market: MarketConfig,
        consumer: TaggedStreamConsumer,
        producer: StreamProducer,
        evaluate_fn: Callable[
            [StoryPayload, MarketConfig], Awaitable[Decision]
        ] | None = None,
    ) -> None:
        self._market = market
        self._consumer = consumer
        self._producer = producer
        self._evaluate_fn = evaluate_fn or _modal_evaluate
        self._stats = ListenerStats()

    @property
    def market(self) -> MarketConfig:
        return self._market

    @property
    def stats(self) -> ListenerStats:
        return self._stats

    async def run(self) -> None:
        """Subscribe to this market's tag channels. Blocks until cancelled."""
        tags = list(self._market.tags)
        group = f"agent-{self._market.address[:12]}"
        consumer_name = f"listener-{self._market.address[:12]}"

        logger.info(
            f"Agent for {self._market.address[:16]}… subscribing to {tags} "
            f"| {self._market.question[:60]}"
        )
        await self._consumer.subscribe(
            tags=tags,
            group=group,
            consumer=consumer_name,
            callback=self._on_story,
        )

    async def _on_story(self, message_id: str, payload: dict[str, Any]) -> None:
        """Handle a story that arrived on one of our subscribed tag channels."""
        self._stats.stories_received += 1

        try:
            story = StoryPayload.from_dict(payload)
        except (KeyError, ValueError) as e:
            logger.warning(f"Malformed story {message_id}: {e}")
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
            return

        if decision.action == "YES":
            self._stats.decisions_yes += 1
        else:
            self._stats.decisions_no += 1

        await self._producer.publish(STREAM_DECISIONS, decision.to_dict())
        logger.info(
            f"[{decision.action}] {self._market.address[:16]}… "
            f"conf={decision.confidence:.2f} ({decision.latency_ms:.0f}ms) "
            f"| {story.headline[:60]}"
        )


async def _modal_evaluate(story: StoryPayload, market: MarketConfig) -> Decision:
    """
    Default evaluate_fn: calls the deployed Modal MarketAgent.

    Requires `modal` installed on the VPS and a deployed trademaxxer-agents app.
    """
    import modal

    AgentCls = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")
    agent = AgentCls()
    result = await agent.evaluate.remote.aio(story.to_dict(), market.to_dict())
    return Decision.from_dict(result)


async def run_all_listeners(
    markets: list[MarketConfig],
    consumer: TaggedStreamConsumer,
    producer: StreamProducer,
    evaluate_fn: Callable[
        [StoryPayload, MarketConfig], Awaitable[Decision]
    ] | None = None,
) -> list[AgentListener]:
    """
    Spawn one AgentListener per market as concurrent tasks.

    Returns the list of listeners (for stats inspection). The tasks
    run until the caller cancels them.
    """
    listeners = [
        AgentListener(market, consumer, producer, evaluate_fn)
        for market in markets
    ]

    logger.info(f"Spawning {len(listeners)} agent listeners")

    tasks = [asyncio.create_task(l.run()) for l in listeners]

    # Let the caller cancel; if any listener dies unexpectedly, log it
    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for t in done:
        if t.exception():
            logger.error(f"Listener crashed: {t.exception()}")

    return listeners
