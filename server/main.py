"""
trademaxxer server — top-level orchestrator

Runs all services in a single async event loop:
  - news_streamer: DBNews websocket → tagger → broadcast (WS + Redis pub/sub)
  - agent listeners: subscribe to Redis channels → Modal (Groq) → log decisions
  - (future) executor: decision queue → proprietary trade API
  - (future) monitor: position tracking + exit logic

Usage:
    cd server
    python main.py                # live: DBNews + Redis + Modal
    python main.py --mock         # mock: fake headlines + fake agents (no Redis/Modal)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger("trademaxxer")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def run(*, use_mock: bool = False) -> None:
    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    # ── News Streamer ──────────────────────────────────────────────
    from news_streamer.config import settings
    from news_streamer.tagger import NewsTagger
    from news_streamer.ws_server import NewsWebSocketServer
    from news_streamer.pubsub import NewsPublisher

    ws_server = NewsWebSocketServer(
        host=settings.websocket_server.host,
        port=settings.websocket_server.port,
    )
    tagger = NewsTagger(settings.tagger, platform_tag_loader=None)
    publisher = NewsPublisher(redis_url=REDIS_URL)

    dbnews_client = None
    if not use_mock:
        from news_streamer.dbnews_client import DBNewsWebSocketClient
        dbnews_client = DBNewsWebSocketClient(settings.dbnews.ws_url)

    # ── Markets ────────────────────────────────────────────────────
    from agents.schemas import MarketConfig, StoryPayload

    test_markets = [
        MarketConfig(
            address="FakeContract1111111111111111111111111111111",
            question="Will the US engage in direct military conflict with Iran before April 2026?",
            current_probability=0.38,
            tags=("geopolitics", "politics"),
        ),
        MarketConfig(
            address="FakeContract2222222222222222222222222222222",
            question="Will oil prices exceed $120/barrel before June 2026?",
            current_probability=0.55,
            tags=("geopolitics", "commodities", "macro"),
        ),
        MarketConfig(
            address="FakeContract3333333333333333333333333333333",
            question="Will the Federal Reserve cut interest rates before July 2026?",
            current_probability=0.42,
            tags=("macro", "economic_data"),
        ),
        MarketConfig(
            address="FakeContract4444444444444444444444444444444",
            question="Will Bitcoin exceed $150k before September 2026?",
            current_probability=0.31,
            tags=("crypto",),
        ),
    ]

    # ── News callback ──────────────────────────────────────────────
    message_count = 0

    async def on_news(news):
        nonlocal message_count
        message_count += 1

        tag_str = ""
        if "HOT" in news.urgency_tags:
            tag_str = "[HOT] "
        elif news.is_priority:
            tag_str = "[HIGH] "

        ticker_str = ""
        if news.pre_tagged_tickers:
            ticker_str = f" | {', '.join(news.pre_tagged_tickers)}"

        logger.info(f"{tag_str}{news.headline[:120]}{ticker_str}")

        tagged = None
        try:
            tagged = tagger.tag(news)
        except Exception as e:
            logger.error(f"Tagger failed: {e}", extra={"news_id": news.id})

        await ws_server.broadcast(news, tagged)

        if tagged is not None and redis_live:
            try:
                await publisher.publish(tagged)
            except Exception as e:
                logger.error(f"Redis publish failed: {e}")

        # In mock mode, run agents inline (no Redis/Modal needed)
        if use_mock and tagged is not None:
            story = StoryPayload(
                id=news.id,
                headline=news.headline,
                body=getattr(news, "body", ""),
                tags=tuple(tagged.categories) if tagged.categories else (),
                source=getattr(news, "source_handle", ""),
                timestamp=datetime.now(timezone.utc),
            )
            for market in test_markets:
                asyncio.create_task(_mock_eval_and_broadcast(story, market))

    # ── Mock agent evaluator (inline, no Redis/Modal) ─────────────

    async def _mock_eval_and_broadcast(story: StoryPayload, market: MarketConfig) -> None:
        from mock_feed import mock_evaluate

        try:
            decision = await mock_evaluate(story, market)
        except Exception as e:
            logger.error(f"Mock eval failed: {e}")
            return

        logger.info(
            f"[{decision.action}] {market.address[:16]}… "
            f"conf={decision.confidence:.2f} ({decision.latency_ms:.0f}ms) "
            f"| {story.headline[:60]}"
        )
        payload = decision.to_dict()
        payload["headline"] = story.headline
        payload["market_question"] = market.question
        await ws_server.broadcast_decision(payload)

    # ── Modal warm-up ──────────────────────────────────────────────

    async def _warmup_modal(market: MarketConfig) -> None:
        """Fire a dummy evaluation to force Modal container boot before real news."""
        dummy = StoryPayload(
            id="warmup-ping",
            headline="warmup ping — ignore",
            body="",
            tags=("warmup",),
            source="trademaxxer",
            timestamp=datetime.now(timezone.utc),
        )

        logger.info("Warming up Modal container...")
        try:
            import modal

            AgentCls = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")
            agent = AgentCls()

            t0 = time.monotonic()
            await agent.evaluate.remote.aio(dummy.to_dict(), market.to_dict())
            warmup_ms = (time.monotonic() - t0) * 1000

            logger.info(f"Modal warm-up complete — {warmup_ms:.0f}ms (container is hot)")
        except Exception as e:
            logger.warning(f"Modal warm-up failed (non-fatal): {e}")

    # ── Register callbacks ─────────────────────────────────────────
    if dbnews_client is not None:
        dbnews_client.on_message(on_news)
        dbnews_client.on_error(lambda e: logger.error(f"DBNews error: {e}"))
        dbnews_client.on_reconnect(lambda: logger.info("DBNews reconnected"))

    # ── Start services ─────────────────────────────────────────────
    logger.info("Starting trademaxxer server")
    await ws_server.start()
    logger.info(
        f"WebSocket server listening on "
        f"ws://{settings.websocket_server.host}:{settings.websocket_server.port}"
    )

    # Connect to Redis (skip in mock mode)
    redis_live = False
    listener_tasks: list[asyncio.Task] = []
    mock_task: asyncio.Task | None = None

    if use_mock:
        logger.info("Mock mode — skipping Redis + Modal (agents run inline)")
    else:
        try:
            await publisher.connect()
            redis_live = True
            logger.info(f"NewsPublisher connected to Redis at {REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to connect NewsPublisher to Redis: {e}")
            logger.error("Agent listeners will NOT start — no Redis connection")

        # Warm up Modal container
        await _warmup_modal(test_markets[0])

        # Start agent listeners (subscribe to Redis channels → Modal)
        if redis_live:
            from agents.listener import run_all_listeners

            async def _broadcast_decision(data):
                await ws_server.broadcast_decision(data)

            listener_tasks = await run_all_listeners(
                markets=test_markets,
                redis_url=REDIS_URL,
                on_decision=_broadcast_decision,
            )
            logger.info(f"{len(listener_tasks)} agent listener(s) running")

    # Connect to news source
    if use_mock:
        from mock_feed import run_mock_feed

        mock_task = asyncio.create_task(
            run_mock_feed(on_news, interval_range=(1.0, 4.0), shutdown=shutdown_event)
        )
        logger.info("Mock news feed started — decisions will be generated inline")
    else:
        await dbnews_client.connect()
        logger.info("Connected to DBNews feed — pipeline is live")

    # ── Wait for shutdown ──────────────────────────────────────────
    await shutdown_event.wait()

    # ── Teardown ───────────────────────────────────────────────────
    logger.info("Shutting down...")

    if mock_task and not mock_task.done():
        mock_task.cancel()
        try:
            await mock_task
        except asyncio.CancelledError:
            pass

    for task in listener_tasks:
        task.cancel()
    if listener_tasks:
        await asyncio.gather(*listener_tasks, return_exceptions=True)
        logger.info("Agent listeners stopped")

    if redis_live:
        await publisher.close()

    await ws_server.stop()

    if dbnews_client is not None:
        await dbnews_client.disconnect()
        stats = dbnews_client.get_stats()
        ws_stats = ws_server.get_stats()
        tagger_stats = tagger.stats
        logger.info(
            f"Final — messages: {stats.get('messages_received', 0)}, "
            f"clients served: {ws_stats.total_connections}, "
            f"tagged: {tagger_stats.items_tagged}, "
            f"tag failures: {tagger_stats.items_failed}"
        )
    else:
        ws_stats = ws_server.get_stats()
        tagger_stats = tagger.stats
        logger.info(
            f"Final (mock) — messages: {message_count}, "
            f"clients served: {ws_stats.total_connections}, "
            f"tagged: {tagger_stats.items_tagged}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="trademaxxer server")
    parser.add_argument("--mock", action="store_true", help="Use mock news feed instead of DBNews")
    args = parser.parse_args()
    asyncio.run(run(use_mock=args.mock))
