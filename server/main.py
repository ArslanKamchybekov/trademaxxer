"""
trademaxxer server — top-level orchestrator

Runs all services in a single async event loop:
  - news_streamer: DBNews websocket → tagger → broadcast (WS + Redis pub/sub)
  - agent listeners: subscribe to Redis channels → Modal (NLI) → log decisions
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

    redis_live = False

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
        MarketConfig(
            address="FakeContract5555555555555555555555555555555",
            question="Will Ethereum flip Bitcoin in market cap before 2027?",
            current_probability=0.08,
            tags=("crypto",),
        ),
        MarketConfig(
            address="FakeContract6666666666666666666666666666666",
            question="Will China invade Taiwan before January 2027?",
            current_probability=0.12,
            tags=("geopolitics", "politics"),
        ),
        MarketConfig(
            address="FakeContract7777777777777777777777777777777",
            question="Will US unemployment exceed 5% before October 2026?",
            current_probability=0.24,
            tags=("macro", "economic_data"),
        ),
        MarketConfig(
            address="FakeContract8888888888888888888888888888888",
            question="Will gold exceed $3500/oz before August 2026?",
            current_probability=0.47,
            tags=("commodities", "macro"),
        ),
        MarketConfig(
            address="FakeContract9999999999999999999999999999999",
            question="Will the EU impose new sanctions on Russia before May 2026?",
            current_probability=0.72,
            tags=("geopolitics", "politics"),
        ),
        MarketConfig(
            address="FakeContractAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            question="Will the S&P 500 hit a new all-time high before July 2026?",
            current_probability=0.61,
            tags=("macro", "economic_data"),
        ),
        MarketConfig(
            address="FakeContractBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            question="Will a major US bank fail before December 2026?",
            current_probability=0.05,
            tags=("macro", "economic_data"),
        ),
        MarketConfig(
            address="FakeContractCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            question="Will natural gas prices exceed $5/MMBtu before winter 2026?",
            current_probability=0.33,
            tags=("commodities", "macro"),
        ),
    ]

    # ── Market state (all OFF by default — user enables via UI) ──
    enabled_markets: set[str] = set()
    market_listeners: dict[str, asyncio.Task] = {}

    def _markets_state_payload() -> dict:
        """Build the markets state dict for broadcasting to clients."""
        return {
            "markets": [m.to_dict() for m in test_markets],
            "enabled": list(enabled_markets),
        }

    async def _handle_command(data: dict) -> None:
        """Handle commands from the UI (toggle_market, etc.)."""
        address = data.get("address", "")
        want_enabled = data.get("enabled", True)
        market = next((m for m in test_markets if m.address == address), None)
        if not market:
            return

        if want_enabled and address not in enabled_markets:
            enabled_markets.add(address)
            logger.info(f"Market enabled: {address[:16]}…")
            if redis_live and not use_mock:
                _spawn_listener(market)
        elif not want_enabled and address in enabled_markets:
            enabled_markets.discard(address)
            logger.info(f"Market disabled: {address[:16]}…")
            task = market_listeners.pop(address, None)
            if task:
                task.cancel()

        ws_server.set_welcome_extra({"markets_state": _markets_state_payload()})
        await ws_server.broadcast_json({
            "type": "markets_state",
            "data": _markets_state_payload(),
        })

    ws_server.set_command_handler(_handle_command)

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
                if market.address in enabled_markets:
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
        logger.info("Warming up Modal container (NLI agent)...")
        try:
            import modal

            Cls = modal.Cls.from_name("trademaxxer-agents-fast", "FastMarketAgent")
            agent = Cls()

            dummy_batch = [{
                "headline": "warmup ping — ignore",
                "question": market.question,
                "probability": 0.5,
                "market_address": "warmup",
                "story_id": "warmup",
            }]

            t0 = time.monotonic()
            await agent.evaluate_batch.remote.aio(dummy_batch)
            warmup_ms = (time.monotonic() - t0) * 1000

            logger.info(f"Modal warm-up complete — {warmup_ms:.0f}ms (container is hot)")
        except Exception as e:
            logger.warning(f"Modal warm-up failed (non-fatal): {e}")

    # ── Dynamic listener spawner ───────────────────────────────────

    def _spawn_listener(market: MarketConfig) -> None:
        """Spawn a single agent listener for a market and track it."""
        from agents.listener import AgentListener

        async def _broadcast_decision(data):
            await ws_server.broadcast_decision(data)

        listener = AgentListener(market, REDIS_URL, on_decision=_broadcast_decision)
        task = asyncio.create_task(
            listener.run(), name=f"agent-{market.address[:12]}"
        )
        market_listeners[market.address] = task
        logger.info(f"Listener spawned for {market.address[:16]}…")

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

        # Start agent listeners for all enabled markets
        if redis_live:
            for market in test_markets:
                if market.address in enabled_markets:
                    _spawn_listener(market)
            logger.info(f"{len(market_listeners)} agent listener(s) running")

    # Set initial markets state for new client connections
    ws_server.set_welcome_extra({"markets_state": _markets_state_payload()})

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

    for task in market_listeners.values():
        task.cancel()
    if market_listeners:
        await asyncio.gather(*market_listeners.values(), return_exceptions=True)
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
