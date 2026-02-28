"""
DBNews Client Module

WebSocket client for DBNews real-time news API.
"""
from news_streamer.dbnews_client.client import DBNewsWebSocketClient
from news_streamer.dbnews_client.normalizer import normalize_news

__all__ = [
    "DBNewsWebSocketClient",
    "normalize_news",
]
