"""
WebSocket Server for News Distribution

Manages client connections and broadcasts news to all connected clients.
Requires JWT authentication via Sec-WebSocket-Protocol header.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Set

# JWT import is conditional - only needed if authentication is configured
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None
import websockets
from websockets.server import WebSocketServerProtocol, serve

from news_streamer.config import settings
from news_streamer.models import RawNewsItem, TaggedNewsItem

logger = logging.getLogger(__name__)

# JWT Configuration (optional for streaming mode)
JWT_SECRET = settings.websocket_server.jwt.secret if settings.websocket_server.jwt else None
JWT_ISSUER = settings.websocket_server.jwt.issuer if settings.websocket_server.jwt else None
JWT_AUDIENCE = settings.websocket_server.jwt.audience if settings.websocket_server.jwt else None


def _base64url_decode(data: str) -> Optional[str]:
    """Decode base64url-encoded string (RFC 4648 Section 5)."""
    try:
        # Add padding if needed
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        # Convert base64url to standard base64
        data = data.replace("-", "+").replace("_", "/")
        return base64.b64decode(data).decode("utf-8")
    except Exception:
        return None


def _extract_token_from_protocol(protocol: str) -> Optional[str]:
    """
    Extract JWT token from Sec-WebSocket-Protocol header.

    Format: "authorization, Bearer_{base64url_encoded_jwt}"

    This is the secure method for WebSocket auth - avoids token in URL/logs.
    """
    if not protocol:
        return None

    # Split by comma and look for Bearer_ prefix
    for part in protocol.split(","):
        part = part.strip()
        if part.startswith("Bearer_"):
            encoded_token = part[7:]  # Remove "Bearer_" prefix
            return _base64url_decode(encoded_token)

    return None


def _verify_jwt_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token and return claims if valid.

    Returns None if token is invalid.
    """
    if not token or not JWT_SECRET or not JWT_AVAILABLE:
        return None

    try:
        decoded = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
                "require": ["exp", "iat", "sub"],
            },
        )
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("WebSocket auth: token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"WebSocket auth: invalid token - {e}")
        return None
    except Exception as e:
        logger.error(f"WebSocket auth: verification failed - {e}")
        return None


def _serialize_raw_news_item(news: RawNewsItem) -> dict[str, Any]:
    """Convert RawNewsItem to JSON-serializable dict for frontend."""
    # Determine urgency level
    urgency = "normal"
    if "HOT" in news.urgency_tags:
        urgency = "breaking"
    elif news.is_priority:
        urgency = "high"
    elif "WARM" in news.urgency_tags:
        urgency = "high"

    return {
        # Core identifiers
        "id": news.id,
        "timestamp": news.timestamp.isoformat(),
        # Content
        "headline": news.headline,
        "body": news.body,
        # Source info
        "sourceType": news.source_type.value,
        "sourceHandle": news.source_handle,
        "sourceDescription": news.source_description,
        "sourceUrl": news.source_url,
        "sourceAvatar": news.source_avatar,
        "mediaUrl": news.media_url,
        # Tickers and tags
        "tickers": list(news.pre_tagged_tickers),
        "tickerReasons": list(news.ticker_reasons),
        "categories": list(news.pre_tagged_categories),
        "highlightedWords": list(news.pre_highlighted_keywords),
        # Priority/urgency
        "urgency": urgency,
        "urgencyTags": list(news.urgency_tags),
        "isHighlight": news.is_priority,
        "isNarrative": news.is_narrative,
        "economicEventType": news.economic_event_type,
    }


def _serialize_tagged_news_item(news: TaggedNewsItem) -> dict[str, Any]:
    """Convert TaggedNewsItem to JSON-serializable dict for frontend."""
    return {
        # Core identifiers
        "id": news.id,
        "timestamp": news.timestamp.isoformat(),
        # Content
        "headline": news.headline,
        "body": news.body,
        # Source info
        "sourceType": news.source_type.value,
        "sourceHandle": news.source_handle,
        "sourceUrl": news.source_url,
        "sourceDescription": news.source_description,
        "sourceAvatar": news.source_avatar,
        "mediaUrl": news.media_url,
        # Tickers and tags
        "tickers": list(news.tickers),
        "tickerReasons": list(news.ticker_reasons),
        "categories": [c.value for c in news.categories],
        "highlightedWords": list(news.keywords),
        # Our sentiment analysis
        "sentiment": news.sentiment.value,
        "sentimentScore": news.sentiment_score,
        # Priority/urgency
        "urgency": news.urgency.value,
        "urgencyTags": list(news.urgency_tags),
        "isHighlight": news.is_highlight,
        "isNarrative": news.is_narrative,
        "economicEventType": news.economic_event_type,
        # Platform tags (matched from TagRules)
        "platformTagIds": list(news.platform_tag_ids),
        "platformTags": list(news.platform_tag_slugs),
    }


@dataclass
class ServerStats:
    """WebSocket server statistics."""

    connected_clients: int
    total_connections: int
    messages_broadcast: int
    start_time: datetime


class NewsWebSocketServer:
    """
    WebSocket server that broadcasts news to connected clients.

    Clients connect and receive real-time news updates as JSON messages.
    Requires JWT authentication via Sec-WebSocket-Protocol header.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self._host = host
        self._port = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._client_users: dict[WebSocketServerProtocol, str] = {}
        self._server: Optional[websockets.WebSocketServer] = None
        self._total_connections = 0
        self._messages_broadcast = 0
        self._start_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._on_command: Optional[Any] = None
        self._welcome_extra: Optional[dict] = None

    def set_command_handler(self, handler) -> None:
        """Register a callback for client commands (toggle_market, etc.)."""
        self._on_command = handler

    def set_welcome_extra(self, data: dict) -> None:
        """Set extra data to include in welcome message (e.g. markets state)."""
        self._welcome_extra = data

    async def _authenticate(
        self,
        path: str,
        request_headers: websockets.Headers,
    ) -> Optional[tuple[int, list[tuple[str, str]], bytes]]:
        """
        Authenticate WebSocket connection during handshake.

        Returns None to accept the connection, or (status, headers, body) to reject.
        If JWT is not configured, allow all connections (streaming mode).
        """
        # If JWT is not configured, allow all connections
        if not JWT_SECRET:
            logger.debug("WebSocket connection accepted (no auth configured)")
            return None

        # Extract token from Sec-WebSocket-Protocol header
        protocol = request_headers.get("Sec-WebSocket-Protocol", "")
        token = _extract_token_from_protocol(protocol)

        if not token:
            logger.warning("WebSocket connection rejected: no token")
            return (
                401,
                [("Content-Type", "application/json")],
                b'{"error": "Authentication required via Sec-WebSocket-Protocol header"}',
            )

        claims = _verify_jwt_token(token)
        if not claims:
            logger.warning("WebSocket connection rejected: invalid token")
            return (
                401,
                [("Content-Type", "application/json")],
                b'{"error": "Invalid or expired token"}',
            )

        logger.debug(f"WebSocket auth successful for user {claims.get('sub')}")

        # Return None to accept the connection
        return None

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._start_time = datetime.now(timezone.utc)

        # Configure server based on whether JWT is enabled
        if JWT_SECRET:
            self._server = await serve(
                self._handle_client,
                self._host,
                self._port,
                ping_interval=30,
                ping_timeout=10,
                process_request=self._authenticate,
                subprotocols=["authorization"],
            )
            logger.info(
                f"WebSocket server started on ws://{self._host}:{self._port} (JWT auth enabled)"
            )
        else:
            self._server = await serve(
                self._handle_client,
                self._host,
                self._port,
                ping_interval=30,
                ping_timeout=10,
            )
            logger.info(
                f"WebSocket server started on ws://{self._host}:{self._port} (no auth - streaming mode)"
            )

    async def stop(self) -> None:
        """Stop the WebSocket server and disconnect all clients."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")

    async def _handle_client(
        self, websocket: WebSocketServerProtocol
    ) -> None:
        """Handle a new client connection."""
        client_id = f"{websocket.remote_address}"

        async with self._lock:
            self._clients.add(websocket)
            self._total_connections += 1
            client_count = len(self._clients)

        logger.info(
            f"Client connected: {client_id} (total: {client_count})"
        )

        # Send welcome message
        welcome = {
            "type": "connected",
            "message": "Connected to Kairos News Stream",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._welcome_extra:
            welcome.update(self._welcome_extra)
        try:
            await websocket.send(json.dumps(welcome))
        except Exception as e:
            logger.warning(f"Failed to send welcome: {e}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await websocket.send(
                            json.dumps({"type": "pong"})
                        )
                    elif msg_type == "toggle_market" and self._on_command:
                        await self._on_command(data)
                except json.JSONDecodeError:
                    pass

        except websockets.ConnectionClosed:
            pass
        finally:
            async with self._lock:
                self._clients.discard(websocket)
                client_count = len(self._clients)

            logger.info(
                f"Client disconnected: {client_id} (total: {client_count})"
            )

    async def broadcast_json(self, payload: dict[str, Any]) -> int:
        """Broadcast an arbitrary JSON message to all connected clients."""
        if not self._clients:
            return 0
        message = json.dumps(payload)
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            return 0
        results = await asyncio.gather(
            *[self._send_to_client(c, message) for c in clients],
            return_exceptions=True,
        )
        return sum(1 for r in results if r is True)

    async def broadcast_decision(self, data: dict[str, Any]) -> int:
        """Broadcast an agent decision to all connected clients."""
        if not self._clients:
            return 0

        message = json.dumps({"type": "decision", "data": data})

        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return 0

        results = await asyncio.gather(
            *[self._send_to_client(client, message) for client in clients],
            return_exceptions=True,
        )
        return sum(1 for r in results if r is True)

    async def broadcast(
        self,
        news: RawNewsItem,
        tagged: TaggedNewsItem | None = None,
    ) -> int:
        """
        Broadcast a news item to all connected clients.

        If tagged is provided, includes sentiment analysis in the broadcast.
        Returns the number of clients that received the message.
        """
        if not self._clients:
            return 0

        # Use tagged data if available, otherwise fall back to raw
        if tagged:
            data = _serialize_tagged_news_item(tagged)
        else:
            data = _serialize_raw_news_item(news)

        message = json.dumps({
            "type": "news",
            "data": data,
        })

        # Get snapshot of clients to avoid modification during iteration
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return 0

        # Send to all clients concurrently
        results = await asyncio.gather(
            *[self._send_to_client(client, message) for client in clients],
            return_exceptions=True,
        )

        success_count = sum(1 for r in results if r is True)
        self._messages_broadcast += 1

        if success_count < len(clients):
            failed = len(clients) - success_count
            logger.debug(
                f"Broadcast: {success_count}/{len(clients)} clients "
                f"({failed} failed)"
            )

        return success_count

    async def _send_to_client(
        self, client: WebSocketServerProtocol, message: str
    ) -> bool:
        """Send message to a single client, return True on success."""
        try:
            await client.send(message)
            return True
        except websockets.ConnectionClosed:
            return False
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            return False

    def get_stats(self) -> ServerStats:
        """Get current server statistics."""
        return ServerStats(
            connected_clients=len(self._clients),
            total_connections=self._total_connections,
            messages_broadcast=self._messages_broadcast,
            start_time=self._start_time or datetime.now(timezone.utc),
        )

    @property
    def client_count(self) -> int:
        """Get current number of connected clients."""
        return len(self._clients)
