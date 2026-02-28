"""
Tests for pub_sub_feed.serializer

Pure unit tests — no Redis, no mocking required.
"""
import json

import pytest

from pub_sub_feed.serializer import SerializationError, deserialize, serialize


class TestSerialize:
    def test_roundtrip(self):
        channel = "news:all"
        data = {"id": "abc", "headline": "Test headline", "score": 1.5}

        raw = serialize(channel, data)
        returned_channel, returned_data = deserialize(raw)

        assert returned_channel == channel
        assert returned_data == data

    def test_roundtrip_with_bytes(self):
        """deserialize() must accept bytes as well as str."""
        channel = "news:urgency:breaking"
        data = {"tickers": ["BTC", "ETH"]}

        raw_str = serialize(channel, data)
        raw_bytes = raw_str.encode("utf-8")

        returned_channel, returned_data = deserialize(raw_bytes)

        assert returned_channel == channel
        assert returned_data == data

    def test_non_serializable_uses_default_str(self):
        """Non-JSON-native objects should be coerced to str, not raise."""
        from datetime import datetime

        channel = "news:all"
        data = {"ts": datetime(2024, 1, 1, 12, 0, 0)}

        raw = serialize(channel, data)
        _, returned_data = deserialize(raw)

        # datetime was coerced to string by default=str
        assert isinstance(returned_data["ts"], str)
        assert "2024" in returned_data["ts"]

    def test_serialize_empty_data(self):
        """Empty dict is valid."""
        raw = serialize("ch", {})
        ch, data = deserialize(raw)
        assert ch == "ch"
        assert data == {}

    def test_serialize_produces_valid_envelope(self):
        """The raw JSON must have the expected envelope shape."""
        raw = serialize("news:all", {"key": "value"})
        envelope = json.loads(raw)

        assert "channel" in envelope
        assert "data" in envelope
        assert envelope["channel"] == "news:all"
        assert envelope["data"] == {"key": "value"}


class TestDeserialize:
    def test_invalid_json_raises(self):
        with pytest.raises(SerializationError, match="Failed to deserialize"):
            deserialize("not valid json {{{{")

    def test_missing_channel_key_raises(self):
        raw = json.dumps({"data": {"key": "value"}})
        with pytest.raises(SerializationError, match="Malformed"):
            deserialize(raw)

    def test_missing_data_key_raises(self):
        raw = json.dumps({"channel": "news:all"})
        with pytest.raises(SerializationError, match="Malformed"):
            deserialize(raw)

    def test_json_array_raises(self):
        """Top-level JSON array is not a valid envelope."""
        raw = json.dumps([{"channel": "news:all", "data": {}}])
        with pytest.raises(SerializationError, match="Malformed"):
            deserialize(raw)

    def test_json_null_raises(self):
        with pytest.raises(SerializationError, match="Malformed"):
            deserialize("null")
