"""
trademaxxer server — top-level orchestrator

Runs all services in a single async event loop:
  - news_streamer: DBNews websocket → tagger → broadcast
  - agent dispatch: news → tag-filter → chunked parallel Modal RPCs → decisions
  - (future) executor: decision queue → proprietary trade API
  - (future) monitor: position tracking + exit logic

Usage:
    cd server
    python main.py                # live: DBNews + Modal (NLI, direct dispatch)
    python main.py --mock         # mock: fake headlines + fake agents (no Modal)
    python main.py --local        # live: DBNews + local ONNX inference (no Modal)
    python main.py --mock --local # mock + local inference
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

BATCH_SIZE = 50

_fast_agent = None
_local_agent = None


def _get_fast_agent():
    """Lazy-init the FastMarketAgent Modal handle (singleton)."""
    global _fast_agent
    if _fast_agent is None:
        import modal
        Cls = modal.Cls.from_name("trademaxxer-agents-fast", "FastMarketAgent")
        _fast_agent = Cls()
    return _fast_agent


def _get_local_agent():
    """Lazy-init the local ONNX NLI agent (singleton)."""
    global _local_agent
    if _local_agent is None:
        from agents.local_inference import LocalNLIAgent
        _local_agent = LocalNLIAgent()
    return _local_agent


async def run(*, use_mock: bool = False, use_local: bool = False) -> None:
    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    # ── News Streamer ──────────────────────────────────────────────
    from news_streamer.config import settings
    from news_streamer.tagger import NewsTagger
    from news_streamer.ws_server import NewsWebSocketServer

    ws_server = NewsWebSocketServer(
        host=settings.websocket_server.host,
        port=settings.websocket_server.port,
    )
    tagger = NewsTagger(settings.tagger, platform_tag_loader=None)

    dbnews_client = None
    if not use_mock:
        from news_streamer.dbnews_client import DBNewsWebSocketClient
        dbnews_client = DBNewsWebSocketClient(settings.dbnews.ws_url)

    # ── Markets ────────────────────────────────────────────────────
    from agents.schemas import MarketConfig, StoryPayload
    from market_registry.kalshi import KalshiMarketRegistry

    # Fetch live markets from Kalshi (no fallback to test markets)
    logger.info("Fetching live markets from Kalshi...")
    markets = []

    try:
        async with KalshiMarketRegistry() as registry:
            live_markets = await registry.fetch_active_markets()

        if live_markets:
            logger.info(f"Loaded {len(live_markets)} markets from Kalshi")
            for i, market in enumerate(live_markets[:3]):  # Show first 3
                logger.info(f"  {i+1}. {market.address}: {market.question[:60]}...")
            markets = live_markets
        else:
            logger.warning("No suitable markets found from Kalshi after filtering")
            logger.info("Server will run without markets - check filtering criteria")
    except Exception as e:
        logger.error(f"Failed to load markets from Kalshi: {e}")
        logger.warning("Server will run without markets - check API connectivity")

    market_by_addr = {m.address: m for m in markets}

    # ── Market state (all OFF by default — user enables via UI) ──
    enabled_markets: set[str] = set()

    def _markets_state_payload() -> dict:
        payload = {
            "markets": [m.to_dict() for m in markets],
            "enabled": list(enabled_markets),
        }
        logger.info(f"Markets state payload: {len(payload['markets'])} markets, {len(payload['enabled'])} enabled")
        return payload

    async def _handle_command(data: dict) -> None:
        address = data.get("address", "")
        want_enabled = data.get("enabled", True)
        if address not in market_by_addr:
            return

        if want_enabled and address not in enabled_markets:
            enabled_markets.add(address)
            logger.info(f"Market enabled: {address[:16]}…")
        elif not want_enabled and address in enabled_markets:
            enabled_markets.discard(address)
            logger.info(f"Market disabled: {address[:16]}…")

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

        # Only log important news to reduce terminal spam
        if "HOT" in news.urgency_tags or news.is_priority:
            logger.info(f"{tag_str}{news.headline[:60]}...")

        tagged = None
        try:
            tagged = tagger.tag(news)
        except Exception as e:
            logger.error(f"Tagger failed: {e}", extra={"news_id": news.id})

        # Fire-and-forget dashboard broadcast
        asyncio.create_task(ws_server.broadcast(news, tagged))

        story = StoryPayload(
            id=news.id,
            headline=news.headline,
            body=getattr(news, "body", ""),
            tags=tuple(tagged.categories) if tagged and tagged.categories else (),
            source=getattr(news, "source_handle", ""),
            timestamp=datetime.now(timezone.utc),
        )

        if use_mock and not use_local:
            for market in markets:
                if market.address in enabled_markets:
                    asyncio.create_task(_mock_eval_and_broadcast(story, market))
        elif enabled_markets:
            asyncio.create_task(_nli_eval_and_broadcast(story))

    # ── Mock agent evaluator (inline, no Modal) ───────────────────

    async def _mock_eval_and_broadcast(story: StoryPayload, market: MarketConfig) -> None:
        from mock_feed import mock_evaluate

        try:
            decision = await mock_evaluate(story, market)
        except Exception as e:
            logger.error(f"Mock eval failed: {e}")
            return

        # Only log high-confidence decisions to reduce spam
        if decision.confidence > 0.7 or decision.action != "SKIP":
            logger.info(f"[{decision.action}] {market.address[:8]}… conf={decision.confidence:.1f}")
        payload = decision.to_dict()
        payload["headline"] = story.headline
        payload["market_question"] = market.question
        asyncio.create_task(ws_server.broadcast_decision(payload))

    # ── NLI direct dispatch (tag-filter → chunk → parallel eval) ──

    async def _nli_eval_and_broadcast(story: StoryPayload) -> None:
        """Tag-filter enabled markets, chunk into batches, evaluate (Modal or local)."""
        story_tags = set(story.tags)
        if story_tags:
            matching = [
                m for m in markets
                if m.address in enabled_markets and story_tags & set(m.tags)
            ]
        else:
            matching = [
                m for m in markets
                if m.address in enabled_markets
            ]
        if not matching:
            return

        chunks = [matching[i:i + BATCH_SIZE] for i in range(0, len(matching), BATCH_SIZE)]

        def _build_batch(markets_chunk):
            return [
                {
                    "headline": story.headline,
                    "question": m.question,
                    "probability": m.current_probability,
                    "market_address": m.address,
                    "story_id": story.id,
                }
                for m in markets_chunk
            ]

        t0 = time.monotonic()
        try:
            if use_local:
                agent = _get_local_agent()
                chunk_results = await asyncio.gather(
                    *[asyncio.to_thread(agent.evaluate_batch, _build_batch(c))
                      for c in chunks]
                )
            else:
                agent = _get_fast_agent()
                chunk_results = await asyncio.gather(
                    *[agent.evaluate_batch.remote.aio(_build_batch(c))
                      for c in chunks]
                )
        except Exception as e:
            logger.error(f"NLI batch eval failed: {e}")
            return
        eval_ms = (time.monotonic() - t0) * 1000

        mode_tag = "local" if use_local else "modal"
        for results in chunk_results:
            for result in results:
                result["latency_ms"] = round(eval_ms, 1)
                result["headline"] = story.headline
                mkt = market_by_addr.get(result["market_address"])
                if mkt:
                    result["market_question"] = mkt.question
                action = result["action"]
                conf = result["confidence"]
                addr = result["market_address"][:16]
                # Only log interesting decisions to reduce spam
                if conf > 0.7 or action != "SKIP":
                    logger.info(f"[{action}] {addr[:8]}… conf={conf:.1f}")
                asyncio.create_task(ws_server.broadcast_decision(result))

    # ── Agent warm-up ─────────────────────────────────────────────

    async def _warmup_agent() -> None:
        dummy_batch = [{
            "headline": "warmup ping — ignore",
            "question": markets[0].question if markets else "Dummy question",
            "probability": 0.5,
            "market_address": "warmup",
            "story_id": "warmup",
        }]
        if use_local:
            logger.info("Loading local ONNX NLI model...")
            try:
                agent = _get_local_agent()
                t0 = time.monotonic()
                await asyncio.to_thread(agent.evaluate_batch, dummy_batch)
                warmup_ms = (time.monotonic() - t0) * 1000
                logger.info(f"Local ONNX warm-up complete — {warmup_ms:.0f}ms (model loaded)")
            except Exception as e:
                logger.warning(f"Local ONNX warm-up failed (non-fatal): {e}")
        else:
            logger.info("Warming up Modal container (ONNX NLI agent)...")
            try:
                agent = _get_fast_agent()
                t0 = time.monotonic()
                await agent.evaluate_batch.remote.aio(dummy_batch)
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

    # Set welcome message with markets data BEFORE starting server
    ws_server.set_welcome_extra({"markets_state": _markets_state_payload()})

    await ws_server.start()
    logger.info(
        f"WebSocket server listening on "
        f"ws://{settings.websocket_server.host}:{settings.websocket_server.port}"
    )

    mock_task: asyncio.Task | None = None

    if use_mock and not use_local:
        logger.info("Mock mode — agents run inline (no Modal)")
    else:
        await _warmup_agent()

    infer_mode = "local ONNX" if use_local else "Modal RPC"
    if use_mock:
        from mock_feed import run_mock_feed

        mock_task = asyncio.create_task(
            run_mock_feed(on_news, interval_range=(1.0, 4.0), shutdown=shutdown_event)
        )
        logger.info(f"Mock news feed started — inference via {infer_mode}")
    else:
        await dbnews_client.connect()
        logger.info(f"Connected to DBNews feed — NLI pipeline is live ({infer_mode})")

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
    parser.add_argument("--local", action="store_true", help="Run ONNX NLI locally instead of Modal RPC")
    args = parser.parse_args()
    asyncio.run(run(use_mock=args.mock, use_local=args.local))
