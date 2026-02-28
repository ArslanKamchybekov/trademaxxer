"""
trademaxxer server — top-level orchestrator

Runs all services in a single async event loop:
  - news_streamer: DBNews websocket → tagger → broadcast
  - (future) classifier: Modal per-market agents
  - (future) executor: decision queue → proprietary trade API
  - (future) monitor: position tracking + exit logic

Usage:
    cd server
    python main.py
"""
from __future__ import annotations

import asyncio
import logging
import signal

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


async def run() -> None:
    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    # ── News Streamer ──────────────────────────────────────────────
    from news_streamer.config import settings
    from news_streamer.dbnews_client import DBNewsWebSocketClient
    from news_streamer.tagger import NewsTagger
    from news_streamer.ws_server import NewsWebSocketServer

    ws_server = NewsWebSocketServer(
        host=settings.websocket_server.host,
        port=settings.websocket_server.port,
    )
    dbnews_client = DBNewsWebSocketClient(settings.dbnews.ws_url)
    tagger = NewsTagger(settings.tagger, platform_tag_loader=None)

    # ── Agent test — evaluate ONE event against a fake market ──────
    from agents.schemas import MarketConfig, StoryPayload, Decision

    test_market = MarketConfig(
        address="FakeContract1111111111111111111111111111111",
        question="Will the Federal Reserve cut interest rates before July 2026?",
        current_probability=0.42,
        tags=("fed", "macro", "economic_data"),
    )
    agent_tested = False

    message_count = 0

    async def on_news(news):
        nonlocal message_count, agent_tested
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

        # ── Fire ONE event at Modal MarketAgent ─────────────────
        if not agent_tested and tagged is not None:
            agent_tested = True
            asyncio.create_task(_test_agent(tagged))

    async def _warmup_modal(market: MarketConfig) -> None:
        """Fire a dummy evaluation to force Modal container boot before real news."""
        import time
        from datetime import datetime, timezone

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

    async def _test_agent(tagged):
        """One-shot test: send the first tagged event to Modal MarketAgent."""
        import time

        story = StoryPayload(
            id=tagged.id,
            headline=tagged.headline,
            body=tagged.body,
            tags=tuple(c.value for c in tagged.categories) or ("macro",),
            source=tagged.source_handle,
            timestamp=tagged.timestamp,
        )

        logger.info(
            f"\n{'='*60}\n"
            f"  AGENT TEST — sending to Modal MarketAgent\n"
            f"  Story:  {story.headline[:80]}\n"
            f"  Market: {test_market.question}\n"
            f"  Prob:   {test_market.current_probability:.0%}\n"
            f"{'='*60}"
        )

        try:
            import modal

            AgentCls = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")
            agent = AgentCls()

            t0 = time.monotonic()
            result = await agent.evaluate.remote.aio(
                story.to_dict(), test_market.to_dict()
            )
            total_ms = (time.monotonic() - t0) * 1000

            dec = Decision.from_dict(result)

            logger.info(
                f"\n{'='*60}\n"
                f"  AGENT RESULT\n"
                f"  Action:     {dec.action}\n"
                f"  Confidence: {dec.confidence:.2f}\n"
                f"  Reasoning:  {dec.reasoning}\n"
                f"  Groq ms:    {dec.latency_ms:.0f}\n"
                f"  Total ms:   {total_ms:.0f}  (includes Modal cold start)\n"
                f"  Prompt:     {dec.prompt_version}\n"
                f"{'='*60}"
            )
        except Exception as e:
            logger.error(f"Agent test failed: {e}", exc_info=True)

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

    # ── Warm up Modal container before news feed connects ──────────
    await _warmup_modal(test_market)

    await dbnews_client.connect()
    logger.info("Connected to DBNews feed")

    # (future) start executor, classifier, monitor here

    # ── Wait for shutdown ──────────────────────────────────────────
    await shutdown_event.wait()

    # ── Teardown ───────────────────────────────────────────────────
    logger.info("Shutting down...")
    await ws_server.stop()
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


if __name__ == "__main__":
    asyncio.run(run())
