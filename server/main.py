"""
trademaxxer server — top-level orchestrator

Runs all services in a single async event loop:
  - news_streamer: DBNews websocket → tagger → broadcast
  - agent dispatch: news → tag-filter → parallel Groq evals → decisions
  - (future) executor: decision queue → proprietary trade API
  - (future) monitor: position tracking + exit logic

Usage:
    cd server
    python main.py                # live: DBNews + Groq via Modal
    python main.py --local        # live: DBNews + Groq locally (requires GROQ_API_KEY)
    python main.py --mock         # mock: fake headlines + fake agents
    python main.py --mock --local # mock headlines + Groq locally
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

_groq_client = None
_modal_agent = None


def _get_groq_client():
    """Lazy-init the local Groq API client (singleton)."""
    global _groq_client
    if _groq_client is None:
        from agents.groq_client import GroqClient
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is required for --local mode"
            )
        _groq_client = GroqClient(api_key=api_key)
    return _groq_client


def _get_modal_agent():
    """Lazy-init the Modal MarketAgent handle (singleton)."""
    global _modal_agent
    if _modal_agent is None:
        import modal
        Cls = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")
        _modal_agent = Cls()
    return _modal_agent


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
        if not settings.dbnews.username or not settings.dbnews.password:
            raise RuntimeError(
                "DBNEWS_USERNAME and DBNEWS_PASSWORD are required for live mode. "
                "Set them in .env or use --mock."
            )
        from news_streamer.dbnews_client import DBNewsWebSocketClient
        dbnews_client = DBNewsWebSocketClient(settings.dbnews.ws_url)

    # ── Markets ────────────────────────────────────────────────────
    from agents.schemas import MarketConfig, StoryPayload
    from market_registry.kalshi import KalshiMarketRegistry

    logger.info("Fetching live markets from Kalshi...")
    markets = []
    live_market_manager = None

    try:
        async with KalshiMarketRegistry() as registry:
            live_markets = await registry.fetch_active_markets()

        if live_markets:
            logger.info(f"Loaded {len(live_markets)} markets from Kalshi")
            for i, market in enumerate(live_markets[:3]):
                logger.info(f"  {i+1}. {market.address}: {market.question[:60]}...")
            markets = live_markets

            # Initialize live market manager for real-time price updates
            if not use_mock:
                from market_registry.kalshi_ws import LiveMarketManager

                api_key = os.environ.get("KALSHI_API_KEY")
                private_key = os.environ.get("KALSHI_PRIVATE_KEY")

                if api_key and private_key:
                    live_market_manager = LiveMarketManager(api_key, private_key)
                    await live_market_manager.__aenter__()
                    logger.info("Initialized Kalshi WebSocket for live price updates")
                else:
                    logger.warning("KALSHI_API_KEY or KALSHI_PRIVATE_KEY missing - using static prices")
        else:
            logger.warning("No suitable markets found from Kalshi after filtering")
            logger.info("Server will run without markets - check filtering criteria")
    except Exception as e:
        logger.error(f"Failed to load markets from Kalshi: {e}")
        logger.warning("Server will run without markets - check API connectivity")

    # ── Demo contracts (prepend, all off by default) ─────────────
    from demo_markets import DEMO_CONTRACTS
    demo_addrs = {m.address for m in DEMO_CONTRACTS}
    markets = list(DEMO_CONTRACTS) + [m for m in markets if m.address not in demo_addrs]
    logger.info(f"Injected {len(DEMO_CONTRACTS)} demo contracts (all off)")

    market_by_addr = {m.address: m for m in markets}

    # ── Market state (all OFF by default) ──────────────────────────
    enabled_markets: set[str] = set()

    # ── In-memory pub/sub: tag channels → market eval callbacks ───
    from pubsub import PubSub
    bus = PubSub()
    market_callbacks: dict[str, object] = {}  # address → callback ref for unsubscribe

    def _markets_state_payload() -> dict:
        payload = {
            "markets": [m.to_dict() for m in markets],
            "enabled": list(enabled_markets),
        }
        logger.info(f"Markets state payload: {len(payload['markets'])} markets, {len(payload['enabled'])} enabled")
        return payload

    # ── Live price updates ─────────────────────────────────────────
    async def _handle_price_update(ticker: str, price: float) -> None:
        """Handle real-time price updates from Kalshi WebSocket."""
        # Update the market in our local state
        market = market_by_addr.get(ticker)
        if market:
            old_price = market.current_probability
            market.current_probability = price

            # Broadcast price update to connected clients
            await ws_server.broadcast_json({
                "type": "price_update",
                "data": {
                    "ticker": ticker,
                    "price": price,
                    "prev_price": old_price,
                    "timestamp": time.time()
                }
            })

            logger.debug(f"Price update {ticker}: {old_price:.3f} → {price:.3f}")

    if live_market_manager:
        live_market_manager.on_price_update(_handle_price_update)

    async def _handle_command(data: dict) -> None:
        address = data.get("address", "")
        want_enabled = data.get("enabled", True)
        if address not in market_by_addr:
            return

        if want_enabled and address not in enabled_markets:
            enabled_markets.add(address)
            _subscribe_market(market_by_addr[address])
            logger.info(f"Market enabled: {address[:16]}… (bus: {bus.channel_count}ch, {bus.subscriber_count} subs)")
        elif not want_enabled and address in enabled_markets:
            enabled_markets.discard(address)
            _unsubscribe_market(market_by_addr[address])
            logger.info(f"Market disabled: {address[:16]}… (bus: {bus.channel_count}ch, {bus.subscriber_count} subs)")

        ws_server.set_welcome_extra({"markets_state": _markets_state_payload()})
        await ws_server.broadcast_json({
            "type": "markets_state",
            "data": _markets_state_payload(),
        })

    ws_server.set_command_handler(_handle_command)

    # ── Per-market eval callback (created once per market) ─────────

    def _make_market_callback(market: MarketConfig):
        """Build an async callback bound to a single market for the bus."""
        async def _on_story(story: StoryPayload) -> None:
            t0 = time.monotonic()

            if use_mock and not use_local:
                from mock_feed import mock_evaluate
                try:
                    decision = await mock_evaluate(story, market)
                except Exception as e:
                    logger.error(f"Mock eval failed: {e}")
                    return
                result = decision.to_dict()
            elif use_local:
                from agents.agent_logic import evaluate as groq_evaluate
                groq = _get_groq_client()
                try:
                    decision = await groq_evaluate(story, market, groq)
                    result = decision.to_dict()
                except Exception as e:
                    logger.warning(f"Groq eval failed for {market.address[:8]}…: {e}")
                    return
            else:
                agent = _get_modal_agent()
                try:
                    result = await agent.evaluate.remote.aio(
                        story.to_dict(), market.to_dict(),
                    )
                except Exception as e:
                    logger.warning(f"Modal eval failed for {market.address[:8]}…: {e}")
                    return

            eval_ms = (time.monotonic() - t0) * 1000
            result["headline"] = story.headline
            result["market_question"] = market.question
            result["prev_price"] = market.current_probability

            action = result.get("action", "SKIP")
            if action != "SKIP":
                theo = result.get("theo")
                theo_str = f" theo={theo:.0%}" if theo is not None else ""
                logger.info(f"[{action}] {market.address[:8]}…{theo_str} {eval_ms:.0f}ms")

            asyncio.create_task(ws_server.broadcast_decision(result))

        return _on_story

    def _subscribe_market(market: MarketConfig) -> None:
        cb = _make_market_callback(market)
        market_callbacks[market.address] = cb
        for tag in market.tags:
            bus.subscribe(tag, cb)

    def _unsubscribe_market(market: MarketConfig) -> None:
        cb = market_callbacks.pop(market.address, None)
        if cb is None:
            return
        for tag in market.tags:
            bus.unsubscribe(tag, cb)

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

        if "HOT" in news.urgency_tags or news.is_priority:
            logger.info(f"{tag_str}{news.headline[:60]}...")

        tagged = None
        try:
            tagged = tagger.tag(news)
        except Exception as e:
            logger.error(f"Tagger failed: {e}", extra={"news_id": news.id})

        asyncio.create_task(ws_server.broadcast(news, tagged))

        tags = tuple(c.value for c in tagged.categories) if tagged and tagged.categories else ()
        if not tags:
            return

        story = StoryPayload(
            id=news.id,
            headline=news.headline,
            body=getattr(news, "body", ""),
            tags=tags,
            source=getattr(news, "source_handle", ""),
            timestamp=datetime.now(timezone.utc),
        )

        await bus.publish(tags, story)

    # ── Agent warm-up ─────────────────────────────────────────────

    async def _warmup_agent() -> None:
        dummy_market = MarketConfig(
            address="warmup",
            question=markets[0].question if markets else "Will it rain tomorrow?",
            current_probability=0.5,
            tags=("warmup",),
        )
        dummy_story = StoryPayload(
            id="warmup",
            headline="warmup ping — ignore",
            body="",
            tags=("warmup",),
            source="warmup",
            timestamp=datetime.now(timezone.utc),
        )

        if use_local:
            logger.info("Warming up Groq client (local)...")
            try:
                from agents.agent_logic import evaluate as groq_evaluate
                groq = _get_groq_client()
                t0 = time.monotonic()
                await groq_evaluate(dummy_story, dummy_market, groq)
                warmup_ms = (time.monotonic() - t0) * 1000
                logger.info(f"Groq warm-up complete — {warmup_ms:.0f}ms")
            except Exception as e:
                logger.warning(f"Groq warm-up failed (non-fatal): {e}")
        else:
            logger.info("Warming up Modal container (Groq agent)...")
            try:
                agent = _get_modal_agent()
                t0 = time.monotonic()
                await agent.evaluate.remote.aio(
                    dummy_story.to_dict(), dummy_market.to_dict()
                )
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

    ws_server.set_welcome_extra({"markets_state": _markets_state_payload()})

    await ws_server.start()
    logger.info(
        f"WebSocket server listening on "
        f"ws://{settings.websocket_server.host}:{settings.websocket_server.port}"
    )

    # ── HTTP API Server ────────────────────────────────────────────
    from aiohttp import web, hdrs
    from aiohttp.web_runner import AppRunner, TCPSite
    from execution.dflow_executor import DFlowExecutor
    from execution.market_mapper import get_market_mapper
    import json

    # Initialize DFlow executor and market mapper
    dflow_executor = None
    market_mapper = get_market_mapper()

    try:
        dflow_executor = DFlowExecutor()
        await dflow_executor.__aenter__()

        # Fetch DFlow markets and create mappings
        dflow_markets_data = await dflow_executor.get_dflow_markets()
        kalshi_markets_data = [m.to_dict() for m in markets if m.address not in demo_addrs]

        mappings = market_mapper.create_mappings(kalshi_markets_data,
            [{"market_id": m.dflow_market_id, "question": m.question} for m in dflow_markets_data])

        market_mapper.print_mapping_summary()
        logger.info(f"DFlow executor initialized with {len(mappings)} market mappings")
    except Exception as e:
        logger.warning(f"Failed to initialize DFlow executor: {e}")

    async def handle_cors(request):
        """Handle CORS preflight requests"""
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            }
        )

    async def execute_trade_handler(request):
        """Execute a trade via DFlow on-chain"""
        try:
            # CORS headers
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            }

            if request.method == 'OPTIONS':
                return web.Response(headers=headers)

            data = await request.json()
            kalshi_ticker = data.get('market_id')
            side = data.get('side')  # "YES" or "NO"
            size = data.get('size', 100)  # USD amount

            if not dflow_executor:
                return web.json_response({
                    'success': False,
                    'error': 'DFlow executor not available'
                }, headers=headers, status=500)

            # Check if the market_id is already a DFlow market ID (starts with KX)
            if kalshi_ticker.startswith('KXFEDCHAIRNOM-'):
                # Direct DFlow market ID - use it directly
                dflow_market_id = kalshi_ticker
            else:
                # Try to get DFlow market ID from Kalshi mapping
                dflow_market_id = market_mapper.get_dflow_market_id(kalshi_ticker)

            # TEST MODE: If no mapping found, create a mock one for demo
            if not dflow_market_id:
                # Check if wallet has 0 SOL balance (test mode)
                wallet_info = await dflow_executor.get_wallet_balance()
                if wallet_info.get("sol_balance", 0) == 0:
                    logger.info(f"TEST MODE: Creating mock DFlow mapping for {kalshi_ticker}")
                    dflow_market_id = f"mock-dflow-{kalshi_ticker[-8:]}"
                else:
                    return web.json_response({
                        'success': False,
                        'error': f'No DFlow mapping found for market {kalshi_ticker}'
                    }, headers=headers, status=400)

            # Execute the trade
            from execution.dflow_executor import DFlowTradeRequest
            trade_req = DFlowTradeRequest(
                market_id=dflow_market_id,
                side=side,
                size=float(size)
            )

            result = await dflow_executor.execute_trade(trade_req)

            # Broadcast trade result to WebSocket clients
            if result.get('success'):
                await ws_server.broadcast_json({
                    "type": "trade_executed",
                    "data": {
                        "venue": "dflow",
                        "kalshi_ticker": kalshi_ticker,
                        "dflow_market_id": dflow_market_id,
                        "side": side,
                        "size": size,
                        "tx_hash": result.get('tx_hash'),
                        "timestamp": result.get('timestamp')
                    }
                })

            return web.json_response(result, headers=headers)

        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, headers={'Access-Control-Allow-Origin': '*'}, status=500)

    async def get_wallet_handler(request):
        """Get wallet balance and info"""
        headers = {'Access-Control-Allow-Origin': '*'}

        if not dflow_executor:
            return web.json_response({
                'error': 'DFlow executor not available'
            }, headers=headers, status=500)

        try:
            balance_info = await dflow_executor.get_wallet_balance()
            return web.json_response(balance_info, headers=headers)
        except Exception as e:
            logger.error(f"Wallet balance error: {e}")
            return web.json_response({
                'error': str(e)
            }, headers=headers, status=500)

    async def get_dflow_markets_handler(request):
        """Get available DFlow markets"""
        headers = {'Access-Control-Allow-Origin': '*'}

        if not dflow_executor:
            return web.json_response({
                'error': 'DFlow executor not available'
            }, headers=headers, status=500)

        try:
            dflow_markets_data = await dflow_executor.get_dflow_markets()
            markets_with_mappings = []

            for market in dflow_markets_data:
                market_info = {
                    'dflow_market_id': market.dflow_market_id,
                    'address': market.address,
                    'question': market.question,
                    'current_probability': market.current_probability,
                    'outcome_a': market.outcome_a,
                    'outcome_b': market.outcome_b,
                    'mapped_kalshi_ticker': None
                }

                # Find if this DFlow market is mapped to any Kalshi ticker
                for ticker, mapping in market_mapper.mappings.items():
                    if mapping.dflow_market_id == market.dflow_market_id:
                        market_info['mapped_kalshi_ticker'] = ticker
                        market_info['mapping_confidence'] = mapping.confidence_score
                        break

                markets_with_mappings.append(market_info)

            return web.json_response({
                'markets': markets_with_mappings,
                'total_mappings': len(market_mapper.mappings)
            }, headers=headers)

        except Exception as e:
            logger.error(f"DFlow markets error: {e}")
            return web.json_response({
                'error': str(e)
            }, headers=headers, status=500)

    # Create HTTP app and routes
    app = web.Application()
    app.router.add_options('/api/execute-trade', handle_cors)
    app.router.add_post('/api/execute-trade', execute_trade_handler)
    app.router.add_get('/api/wallet', get_wallet_handler)
    app.router.add_get('/api/dflow-markets', get_dflow_markets_handler)

    # Start HTTP server
    http_runner = AppRunner(app)
    await http_runner.setup()
    http_site = TCPSite(http_runner, settings.websocket_server.host, 8767)
    await http_site.start()
    logger.info(f"HTTP API server listening on http://{settings.websocket_server.host}:8767")

    mock_task: asyncio.Task | None = None
    demo_task: asyncio.Task | None = None

    if use_mock and not use_local:
        logger.info("Mock mode — agents run inline (no Groq)")
    else:
        await _warmup_agent()

    infer_mode = "Groq local" if use_local else "Groq via Modal"

    if use_mock:
        from mock_feed import run_mock_feed

        mock_task = asyncio.create_task(
            run_mock_feed(on_news, interval_range=(1.0, 4.0), shutdown=shutdown_event)
        )
        logger.info(f"Mock news feed started — inference via {infer_mode}")
    else:
        await dbnews_client.connect()
        logger.info(f"Connected to DBNews feed — pipeline is live ({infer_mode})")

    # Start demo headline injector alongside the real/mock feed
    from demo_markets import run_demo_injector
    demo_task = asyncio.create_task(
        run_demo_injector(on_news, interval_range=(8.0, 25.0), shutdown=shutdown_event)
    )
    logger.info("Demo headline injector started")

    # Start live market price updates
    if live_market_manager and markets:
        try:
            # Filter out demo markets for live updates (they don't have real tickers)
            real_markets = [m for m in markets if m.address not in demo_addrs]
            if real_markets:
                await live_market_manager.start(real_markets)
                logger.info(f"Started live price updates for {len(real_markets)} real markets")
        except Exception as e:
            logger.error(f"Failed to start live market updates: {e}")
            # Continue without live updates

    # ── Wait for shutdown ──────────────────────────────────────────
    await shutdown_event.wait()

    # ── Teardown ───────────────────────────────────────────────────
    logger.info("Shutting down...")

    for task in (mock_task, demo_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    await ws_server.stop()

    # Stop HTTP API server
    if 'http_runner' in locals():
        try:
            await http_runner.cleanup()
            logger.info("Stopped HTTP API server")
        except Exception as e:
            logger.warning(f"Error stopping HTTP server: {e}")

    # Stop DFlow executor
    if dflow_executor:
        try:
            await dflow_executor.__aexit__(None, None, None)
            logger.info("Stopped DFlow executor")
        except Exception as e:
            logger.warning(f"Error stopping DFlow executor: {e}")

    # Stop live market updates
    if live_market_manager:
        try:
            await live_market_manager.stop()
            await live_market_manager.__aexit__(None, None, None)
            logger.info("Stopped live market updates")
        except Exception as e:
            logger.warning(f"Error stopping live market manager: {e}")

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
    parser.add_argument("--local", action="store_true", help="Call Groq API locally instead of via Modal")
    args = parser.parse_args()
    asyncio.run(run(use_mock=args.mock, use_local=args.local))
