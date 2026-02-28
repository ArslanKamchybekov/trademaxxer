"""
News Streamer Service Entry Point

Receives news from DBNews and broadcasts to connected frontend clients.
No database storage - just live streaming.
"""
from __future__ import annotations

import asyncio
import logging
import signal

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv("../.env")  # Load from server/.env
except ImportError:
    pass  # python-dotenv not available

# Configure logging before importing config (which may fail)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Main entry point - runs the news streaming pipeline with tagging.

    1. Connects to DBNews WebSocket to receive news
    2. Tags news with sentiment and categories
    3. Starts a WebSocket server for frontend clients
    4. Broadcasts tagged news items to all connected clients
    5. Publishes tagged news items to Redis pub/sub feeds
    """
    from news_streamer.config import settings
    from news_streamer.dbnews_client import DBNewsWebSocketClient
    from news_streamer.models import RawNewsItem
    from news_streamer.ws_server import NewsWebSocketServer
    from news_streamer.tagger import NewsTagger
    from news_streamer.pubsub import NewsPublisher

    logger.info("Starting news streamer with tagging")

    # Create components
    dbnews_client = DBNewsWebSocketClient(settings.dbnews.ws_url)
    ws_server = NewsWebSocketServer(
        host=settings.websocket_server.host,
        port=settings.websocket_server.port,
    )

    # Create tagger (no platform tags needed for streaming)
    tagger = NewsTagger(settings.tagger, platform_tag_loader=None)

    # Create Redis publisher
    news_publisher = NewsPublisher(settings.redis.url)
    await news_publisher.connect()

    # Message counter for stats
    message_count = 0

    async def handle_message(news: RawNewsItem) -> None:
        nonlocal message_count
        message_count += 1

        # Log the news item
        urgency_str = ""
        if "HOT" in news.urgency_tags:
            urgency_str = "[HOT] "
        elif news.is_priority:
            urgency_str = "[HIGH] "

        tickers_str = ""
        if news.pre_tagged_tickers:
            tickers_str = f" | Tickers: {', '.join(news.pre_tagged_tickers)}"

        logger.info(
            f"{urgency_str}{news.headline[:100]}{tickers_str}",
            extra={
                "news_id": news.id,
                "source": news.source_type.value,
                "handle": news.source_handle,
                "message_count": message_count,
            },
        )

        # Tag the news with sentiment analysis
        tagged_news = None
        try:
            tagged_news = tagger.tag(news)
            logger.debug(
                f"Tagged news: sentiment={tagged_news.sentiment.value}, "
                f"tickers={len(tagged_news.tickers)}, "
                f"categories={[c.value for c in tagged_news.categories]}",
                extra={"news_id": news.id},
            )
        except Exception as e:
            logger.error(
                f"Failed to tag news: {e}",
                extra={"news_id": news.id, "error": str(e)},
            )

        # Broadcast to WebSocket clients (this should be removed and we should only broadcast ai output to clients) and publish to Redis feeds
        client_count = await ws_server.broadcast(news, tagged_news)
        if client_count > 0:
            logger.debug(
                f"Broadcast to {client_count} clients",
                extra={"news_id": news.id},
            )

        if tagged_news is not None:
            try:
                await news_publisher.publish(tagged_news)
            except Exception as e:
                logger.error(
                    f"Failed to publish to Redis: {e}",
                    extra={"news_id": news.id, "error": str(e)},
                )

    async def handle_error(error: Exception) -> None:
        logger.error(
            "DBNews connection error",
            extra={"error": str(error)},
        )

    async def handle_reconnect() -> None:
        logger.info("Reconnected to DBNews")

    # Set up handlers
    dbnews_client.on_message(handle_message)
    dbnews_client.on_error(handle_error)
    dbnews_client.on_reconnect(handle_reconnect)

    # Start WebSocket server for clients
    await ws_server.start()

    # Connect to DBNews
    await dbnews_client.connect()

    # Keep running until interrupted
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await shutdown_event.wait()
    finally:
        logger.info("Shutting down...")

        # Stop WebSocket server
        await ws_server.stop()

        # Disconnect from DBNews
        await dbnews_client.disconnect()

        # Close Redis publisher
        await news_publisher.close()

        # Log final stats
        dbnews_stats = dbnews_client.get_stats()
        ws_stats = ws_server.get_stats()
        tagger_stats = tagger.stats
        logger.info(
            "Final stats",
            extra={
                "dbnews_messages": dbnews_stats.get("messages_received", 0),
                "clients_served": ws_stats.total_connections,
                "broadcasts": ws_stats.messages_broadcast,
                "items_tagged": tagger_stats.items_tagged,
                "tagging_failures": tagger_stats.items_failed,
            },
        )


if __name__ == "__main__":
    try:
        from news_streamer.config import settings  # noqa: F401
    except SystemExit:
        raise SystemExit(1)

    asyncio.run(main())
