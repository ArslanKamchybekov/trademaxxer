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
