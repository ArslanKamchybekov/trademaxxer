"""
DBNews WebSocket Client

Real-time WebSocket connection to DBNews streaming API.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    InvalidStatusCode,
)

from news_streamer.core.types import (
    AuthenticationError,
    ConnectionError,
    ReconnectionState,
    ValidationError,
)
from news_streamer.dbnews_client.normalizer import normalize_news
from news_streamer.models.news import RawNewsItem

logger = logging.getLogger(__name__)

# Type aliases for callbacks
MessageCallback = Callable[[RawNewsItem], Awaitable[None]]
ErrorCallback = Callable[[Exception], Awaitable[None]]
ReconnectCallback = Callable[[], Awaitable[None]]


class DBNewsWebSocketClient:
    """
    WebSocket client for DBNews real-time news streaming.

    Manages persistent connection with automatic reconnection.
    """

    def __init__(
        self,
        ws_url: str,
        *,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        close_timeout: float = 5.0,
    ) -> None:
        """
        Initialize the client.

        Args:
            ws_url: Full WebSocket URL with auth (wss://user:pass@dbws.io/all)
            ping_interval: Interval between ping frames (seconds)
            ping_timeout: Timeout for pong response (seconds)
            close_timeout: Timeout for close handshake (seconds)
        """
        self._ws_url = ws_url
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._close_timeout = close_timeout

        # Connection state
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._should_reconnect = True
        self._reconnection_state = ReconnectionState()

        # Callbacks
        self._on_message: Optional[MessageCallback] = None
        self._on_error: Optional[ErrorCallback] = None
        self._on_reconnect: Optional[ReconnectCallback] = None

        # Stats
        self._messages_received = 0
        self._last_message_time: Optional[datetime] = None
        self._connection_start_time: Optional[datetime] = None

        # Task management
        self._receive_task: Optional[asyncio.Task[None]] = None

    @property
    def connected(self) -> bool:
        """Check if currently connected."""
        return self._connected and self._ws is not None

    @property
    def messages_received(self) -> int:
        """Get total messages received."""
        return self._messages_received

    @property
    def last_message_time(self) -> Optional[datetime]:
        """Get timestamp of last received message."""
        return self._last_message_time

    def on_message(self, callback: MessageCallback) -> None:
        """Register callback for incoming news messages."""
        self._on_message = callback

    def on_error(self, callback: ErrorCallback) -> None:
        """Register callback for connection errors."""
        self._on_error = callback

    def on_reconnect(self, callback: ReconnectCallback) -> None:
        """Register callback for reconnection events."""
        self._on_reconnect = callback

    async def connect(self) -> None:
        """
        Establish WebSocket connection to DBNews.

        Raises:
            AuthenticationError: If credentials are invalid (401)
            ConnectionError: If connection fails after retries
        """
        self._should_reconnect = True
        await self._connect_with_retry()

    async def _connect_with_retry(self) -> None:
        """Connect with exponential backoff retry."""
        while self._should_reconnect:
            try:
                await self._establish_connection()
                # Success - reset reconnection state
                self._reconnection_state.reset()
                return

            except AuthenticationError:
                # Don't retry on auth errors
                raise

            except Exception as e:
                if not self._should_reconnect:
                    return

                delay = self._reconnection_state.next_delay()
                attempt = self._reconnection_state.attempt_count

                logger.warning(
                    "Connection failed, retrying",
                    extra={
                        "attempt": attempt,
                        "delay_seconds": delay,
                        "error": str(e),
                    },
                )

                if self._on_error:
                    try:
                        await self._on_error(e)
                    except Exception as callback_error:
                        logger.error(
                            "Error callback failed",
                            extra={"error": str(callback_error)},
                        )

                await asyncio.sleep(delay)

    async def _establish_connection(self) -> None:
        """Establish single connection attempt."""
        # Mask password in logs
        safe_url = self._ws_url
        if "@" in safe_url:
            parts = safe_url.split("@")
            safe_url = f"wss://***:***@{parts[-1]}"

        logger.info("Connecting to DBNews", extra={"url": safe_url})

        try:
            self._ws = await websockets.connect(
                self._ws_url,
                ping_interval=self._ping_interval,
                ping_timeout=self._ping_timeout,
                close_timeout=self._close_timeout,
            )

            self._connected = True
            self._connection_start_time = datetime.now(timezone.utc)

            logger.info(
                "Connected to DBNews",
                extra={"url": safe_url},
            )

            # Notify reconnection if this was a reconnect
            if self._reconnection_state.attempt_count > 0 and self._on_reconnect:
                try:
                    await self._on_reconnect()
                except Exception as e:
                    logger.error(
                        "Reconnect callback failed",
                        extra={"error": str(e)},
                    )

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

        except InvalidStatusCode as e:
            if e.status_code == 401:
                raise AuthenticationError(
                    "Invalid DBNews credentials",
                    service="dbnews",
                ) from e
            raise ConnectionError(
                f"Connection failed with status {e.status_code}",
                service="dbnews",
                retry_count=self._reconnection_state.attempt_count,
            ) from e

        except Exception as e:
            raise ConnectionError(
                f"Failed to connect: {e}",
                service="dbnews",
                retry_count=self._reconnection_state.attempt_count,
            ) from e

    async def _receive_loop(self) -> None:
        """Main receive loop for WebSocket messages."""
        if self._ws is None:
            return

        try:
            async for message in self._ws:
                if not self._should_reconnect:
                    break

                await self._handle_message(message)

        except ConnectionClosedError as e:
            logger.warning(
                f"Connection closed: code={e.code}, reason={e.reason}",
            )
        except ConnectionClosed as e:
            logger.warning(
                f"Connection closed: code={getattr(e, 'code', None)}, reason={getattr(e, 'reason', None)}",
            )
        except Exception as e:
            logger.error(
                "Unexpected error in receive loop",
                extra={"error": str(e)},
                exc_info=True,
            )
        finally:
            self._connected = False

            # Trigger reconnection if needed
            if self._should_reconnect:
                logger.info("Attempting reconnection")
                asyncio.create_task(self._connect_with_retry())

    async def _handle_message(self, message: str | bytes) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            message: Raw message from WebSocket
        """
        self._messages_received += 1
        self._last_message_time = datetime.now(timezone.utc)

        # Parse JSON
        try:
            if isinstance(message, bytes):
                message = message.decode("utf-8")

            data = json.loads(message)

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse message as JSON",
                extra={
                    "error": str(e),
                    "message_preview": str(message)[:200],
                },
            )
            return

        # Normalize to RawNewsItem
        try:
            news_item = normalize_news(data)

        except ValidationError as e:
            logger.warning(
                "Failed to normalize message",
                extra={
                    "error": str(e),
                    "news_id": data.get("_id", "unknown"),
                    "field": e.field,
                },
            )
            return

        except Exception as e:
            logger.error(
                "Unexpected error normalizing message",
                extra={
                    "error": str(e),
                    "news_id": data.get("_id", "unknown"),
                },
                exc_info=True,
            )
            return

        # Call message callback
        if self._on_message:
            try:
                await self._on_message(news_item)
            except Exception as e:
                logger.error(
                    "Message callback failed",
                    extra={
                        "error": str(e),
                        "news_id": news_item.id,
                    },
                    exc_info=True,
                )

    async def disconnect(self) -> None:
        """
        Gracefully close the connection.

        Waits for in-flight messages to complete.
        """
        logger.info("Disconnecting from DBNews")

        self._should_reconnect = False
        self._connected = False

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.warning(
                    "Error closing WebSocket",
                    extra={"error": str(e)},
                )
            finally:
                self._ws = None

        logger.info(
            "Disconnected from DBNews",
            extra={"messages_received": self._messages_received},
        )

    def get_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        uptime_seconds = None
        if self._connection_start_time and self._connected:
            uptime_seconds = (
                datetime.now(timezone.utc) - self._connection_start_time
            ).total_seconds()

        return {
            "connected": self._connected,
            "messages_received": self._messages_received,
            "last_message_time": (
                self._last_message_time.isoformat()
                if self._last_message_time
                else None
            ),
            "uptime_seconds": uptime_seconds,
            "reconnect_attempts": self._reconnection_state.attempt_count,
        }
