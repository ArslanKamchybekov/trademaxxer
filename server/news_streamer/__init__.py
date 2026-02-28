"""
News Streamer Service

Real-time news distribution system for the Kairos trading platform.
Streams financial news to traders via WebSocket, tags/categorizes stories for filtering,
and persists to ClickHouse for historical analysis.

Architecture:
    DBNews (external) -> dbnews_client -> tagger -> [ws_server, clickhouse_writer]

Components:
    - dbnews_client: WebSocket client for DBNews API
    - tagger: News analysis and categorization engine
    - platform_tags: TagRule matching from PostgreSQL
    - clickhouse_writer: Persistence layer for historical queries
    - ws_server: WebSocket server for frontend clients
    - api: REST endpoints for historical news queries
"""
