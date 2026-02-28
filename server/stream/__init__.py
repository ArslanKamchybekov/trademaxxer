"""
trademaxxer stream — abstract interface for the Redis stream transport.

The C++ pybind11 binding will satisfy these protocols when it lands.
Until then, use InMemoryStream from stream.stub for local development.
"""

from stream.interface import TaggedStreamConsumer, StreamProducer, MarketRegistryReader

__all__ = ["TaggedStreamConsumer", "StreamProducer", "MarketRegistryReader"]
