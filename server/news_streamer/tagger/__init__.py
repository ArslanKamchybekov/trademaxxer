"""
News Tagger Service

Core tagging engine that analyzes news content and extracts structured metadata.
Transforms RawNewsItem into TaggedNewsItem with tickers, categories, sentiment.

Re-exports:
    - NewsTagger: Main tagging orchestrator
    - TaggerStats: Tagger statistics
    - TaggingError: Tagging error exception

Usage:
    from tagger import NewsTagger

    tagger = NewsTagger(config)
    tagged_news = tagger.tag(raw_news)
"""
from .tagger import NewsTagger, TaggerStats, TaggingError

__all__ = [
    "NewsTagger",
    "TaggerStats",
    "TaggingError",
]
