"""
Feed Serializer

Converts between Python dicts and the JSON strings stored in Redis.
pub_sub_feed is intentionally decoupled from news_streamer models — it
operates on plain dicts. The publisher/subscriber layer in news_streamer is
responsible for converting TaggedNewsItem <-> dict before handing off here.

Wire format (envelope):
  {
    "channel": "news:all",
    "data": { ...item fields... }
  }
"""
from __future__ import annotations

import json
from typing import Any


class SerializationError(Exception):
    """Raised when serialization or deserialization fails."""


def serialize(channel: str, data: dict[str, Any]) -> str:
    """
    Encode a channel name and data dict into a JSON string for Redis.

    Raises SerializationError if encoding fails.
    """
    try:
        return json.dumps({"channel": channel, "data": data}, default=str)
    except (TypeError, ValueError) as exc:
        raise SerializationError(f"Failed to serialize feed message: {exc}") from exc


def deserialize(raw: str | bytes) -> tuple[str, dict[str, Any]]:
    """
    Decode a JSON string from Redis into (channel, data).

    Raises SerializationError if decoding fails or the envelope is malformed.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SerializationError(f"Failed to deserialize feed message: {exc}") from exc

    if not isinstance(envelope, dict) or "channel" not in envelope or "data" not in envelope:
        raise SerializationError(
            f"Malformed feed envelope — expected {{channel, data}}, got: {list(envelope.keys())}"
        )

    return envelope["channel"], envelope["data"]
