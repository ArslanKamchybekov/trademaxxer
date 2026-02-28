"""
Kalshi WebSocket client for real-time market price updates.

Provides live market data streaming to replace static prices with real-time updates.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable

import aiohttp
import websockets

from agents.schemas import MarketConfig


logger = logging.getLogger(__name__)


class KalshiWebSocketClient:
    """
    Real-time Kalshi market data WebSocket client.

    Connects to Kalshi's WebSocket feed and streams live price updates
    for enabled markets to update current_probability in real-time.
    """

    def __init__(
        self,
        api_key: str,
        private_key: str,
        base_url: str = "https://api.elections.kalshi.com/trade-api/v2",
        ws_url: str = "wss://api.elections.kalshi.com/trade-api/ws",
        reconnect_interval: float = 5.0,
    ):
        self.api_key = api_key
        self.private_key = private_key.replace("\\n", "\n")  # Handle escaped newlines
        self.base_url = base_url
        self.ws_url = ws_url
        self.reconnect_interval = reconnect_interval

        self._session: aiohttp.ClientSession | None = None
        self._websocket: websockets.WebSocketServerProtocol | None = None
        self._access_token: str | None = None
        self._token_expires: float = 0
        self._subscribed_markets: set[str] = set()
        self._running = False

        # Callbacks
        self._on_price_update: Callable[[str, float], None] | None = None
        self._on_error: Callable[[Exception], None] | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        if self._session:
            await self._session.close()

    def on_price_update(self, callback: Callable[[str, float], None]) -> None:
        """Register callback for price updates: callback(ticker, price)"""
        self._on_price_update = callback

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register callback for errors: callback(exception)"""
        self._on_error = callback

    async def connect(self) -> None:
        """Connect to Kalshi WebSocket and start listening for price updates."""
        if self._running:
            return

        self._running = True
        logger.info("Starting Kalshi WebSocket client...")

        while self._running:
            try:
                # Get access token
                await self._authenticate()

                # Connect to WebSocket
                await self._connect_websocket()

                # Listen for messages
                await self._listen_loop()

            except Exception as e:
                logger.error(f"Kalshi WebSocket error: {e}")
                if self._on_error:
                    self._on_error(e)

                if self._running:
                    logger.info(f"Reconnecting in {self.reconnect_interval}s...")
                    await asyncio.sleep(self.reconnect_interval)

            finally:
                if self._websocket:
                    await self._websocket.close()
                    self._websocket = None

    async def disconnect(self) -> None:
        """Disconnect from Kalshi WebSocket."""
        self._running = False
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
        logger.info("Kalshi WebSocket client disconnected")

    async def subscribe_to_markets(self, tickers: list[str]) -> None:
        """Subscribe to price updates for specific market tickers."""
        if not self._websocket:
            logger.warning("Cannot subscribe: WebSocket not connected")
            return

        new_tickers = set(tickers) - self._subscribed_markets
        if not new_tickers:
            return

        # Subscribe to markets
        subscribe_msg = {
            "id": int(time.time()),
            "cmd": "subscribe",
            "params": {
                "channels": [f"orderbook_delta:{ticker}" for ticker in new_tickers]
            }
        }

        try:
            await self._websocket.send(json.dumps(subscribe_msg))
            self._subscribed_markets.update(new_tickers)
            logger.info(f"Subscribed to {len(new_tickers)} markets: {', '.join(list(new_tickers)[:3])}{'...' if len(new_tickers) > 3 else ''}")
        except Exception as e:
            logger.error(f"Failed to subscribe to markets: {e}")

    async def _authenticate(self) -> None:
        """Get JWT access token using API key and private key."""
        if self._access_token and time.time() < self._token_expires - 300:  # 5min buffer
            return

        if not self._session:
            raise RuntimeError("Session not initialized")

        # Create JWT payload
        import jwt
        from cryptography.hazmat.primitives import serialization

        now = int(time.time())
        payload = {
            "sub": self.api_key,
            "iat": now,
            "exp": now + 3600,  # 1 hour
            "aud": ["kalshi-api"]
        }

        # Load private key
        private_key = serialization.load_pem_private_key(
            self.private_key.encode(),
            password=None
        )

        # Sign JWT
        token = jwt.encode(payload, private_key, algorithm="RS256")

        # Exchange JWT for access token
        async with self._session.post(
            f"{self.base_url}/login",
            headers={"Authorization": f"Bearer {token}"}
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        self._access_token = data["token"]
        self._token_expires = time.time() + 3600
        logger.info("Successfully authenticated with Kalshi API")

    async def _connect_websocket(self) -> None:
        """Connect to Kalshi WebSocket with authentication."""
        if not self._access_token:
            raise RuntimeError("Not authenticated")

        headers = {"Authorization": f"Bearer {self._access_token}"}

        self._websocket = await websockets.connect(
            self.ws_url,
            extra_headers=headers,
            ping_interval=20,
            ping_timeout=10
        )

        logger.info("Connected to Kalshi WebSocket")

    async def _listen_loop(self) -> None:
        """Main message listening loop."""
        if not self._websocket:
            return

        async for message in self._websocket:
            try:
                data = json.loads(message)
                await self._handle_message(data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {message}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    async def _handle_message(self, data: dict) -> None:
        """Handle incoming WebSocket messages."""
        msg_type = data.get("type")

        if msg_type == "orderbook_delta":
            # Handle price update
            ticker = data.get("ticker")
            market_data = data.get("msg", {})

            # Extract current price from orderbook
            yes_ask = market_data.get("yes_ask")
            yes_bid = market_data.get("yes_bid")

            if ticker and (yes_ask is not None or yes_bid is not None):
                # Use mid price or best available price
                if yes_ask is not None and yes_bid is not None:
                    price = (float(yes_ask) + float(yes_bid)) / 2
                elif yes_ask is not None:
                    price = float(yes_ask)
                elif yes_bid is not None:
                    price = float(yes_bid)
                else:
                    return

                if self._on_price_update:
                    self._on_price_update(ticker, price)

        elif msg_type == "error":
            error_msg = data.get("msg", "Unknown error")
            logger.error(f"WebSocket error from Kalshi: {error_msg}")

        elif msg_type in ("subscribed", "unsubscribed"):
            logger.debug(f"Subscription {msg_type}: {data.get('msg')}")


class LiveMarketManager:
    """
    Manages live market data updates using Kalshi WebSocket feed.

    Integrates with existing MarketConfig objects to update prices in real-time.
    """

    def __init__(self, api_key: str, private_key: str):
        self.api_key = api_key
        self.private_key = private_key
        self._markets: dict[str, MarketConfig] = {}
        self._ws_client: KalshiWebSocketClient | None = None
        self._price_update_callback: Callable[[str, float], None] | None = None

    async def __aenter__(self):
        self._ws_client = KalshiWebSocketClient(self.api_key, self.private_key)
        await self._ws_client.__aenter__()

        # Setup callbacks
        self._ws_client.on_price_update(self._handle_price_update)
        self._ws_client.on_error(self._handle_error)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._ws_client:
            await self._ws_client.__aexit__(exc_type, exc_val, exc_tb)

    def on_price_update(self, callback: Callable[[str, float], None]) -> None:
        """Register callback for when market prices are updated."""
        self._price_update_callback = callback

    async def start(self, markets: list[MarketConfig]) -> None:
        """Start live price updates for given markets."""
        if not self._ws_client:
            raise RuntimeError("Not initialized")

        # Store markets
        for market in markets:
            self._markets[market.address] = market

        # Connect WebSocket
        asyncio.create_task(self._ws_client.connect())

        # Subscribe to markets
        tickers = [m.address for m in markets]
        await asyncio.sleep(1)  # Wait for connection
        await self._ws_client.subscribe_to_markets(tickers)

        logger.info(f"Started live price updates for {len(markets)} markets")

    async def stop(self) -> None:
        """Stop live price updates."""
        if self._ws_client:
            await self._ws_client.disconnect()

    def _handle_price_update(self, ticker: str, price: float) -> None:
        """Handle price update from WebSocket."""
        if ticker in self._markets:
            market = self._markets[ticker]
            old_price = market.current_probability
            market.current_probability = price

            logger.debug(f"Price update {ticker}: {old_price:.3f} → {price:.3f}")

            if self._price_update_callback:
                self._price_update_callback(ticker, price)

    def _handle_error(self, error: Exception) -> None:
        """Handle WebSocket errors."""
        logger.error(f"Live market manager error: {error}")


async def test_kalshi_websocket():
    """Test function for Kalshi WebSocket integration."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.environ.get("KALSHI_API_KEY")
    private_key = os.environ.get("KALSHI_PRIVATE_KEY")

    if not api_key or not private_key:
        print("KALSHI_API_KEY and KALSHI_PRIVATE_KEY required in .env")
        return

    def on_price_update(ticker: str, price: float):
        print(f"💰 {ticker}: ${price:.3f}")

    async with LiveMarketManager(api_key, private_key) as manager:
        # Create dummy market for testing
        from market_registry.kalshi import KalshiMarketRegistry

        async with KalshiMarketRegistry() as registry:
            markets = await registry.fetch_active_markets()

        if not markets:
            print("No markets found for testing")
            return

        manager.on_price_update(on_price_update)
        await manager.start(markets[:5])  # Test with first 5 markets

        print(f"Listening for price updates on {len(markets[:5])} markets...")
        print("Press Ctrl+C to stop")

        try:
            await asyncio.sleep(60)  # Listen for 1 minute
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    asyncio.run(test_kalshi_websocket())