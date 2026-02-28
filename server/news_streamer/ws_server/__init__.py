"""
WebSocket Server for News Distribution

Broadcasts news items to connected frontend clients.
"""
from news_streamer.ws_server.server import NewsWebSocketServer

__all__ = ["NewsWebSocketServer"]
