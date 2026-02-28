#!/usr/bin/env python3
"""
Pub/Sub integration smoke test.

Spins up one NewsPublisher and three FeedSubscribers, pushes five
TaggedNewsItems with different urgency/category/ticker combinations, and
prints what each subscriber received.

Demonstrates:
  - Fan-out: every subscriber independently receives every matching message.
  - Multi-channel delivery: an item published to N channels a subscriber
    listens on is delivered N times (once per matching channel).
  - Per-subscriber filtering: subscribers only see feeds they asked for.

Two modes:

  --fake   In-process fakeredis (no external server needed, default on Fedora
           when Docker/Podman isn't handy).

  Live Redis (default):
    On Fedora/Linux with podman:   podman run --rm -p 6379:6379 redis
    With Docker:                   docker run --rm -p 6379:6379 redis

Usage (from server/):
    python integration_test_pubsub.py --fake
    python integration_test_pubsub.py --redis-url redis://localhost:6379/0
    python integration_test_pubsub.py --delay 0.2
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

# Both pub_sub_feed and news_streamer live under server/, so run from there.
sys.path.insert(0, str(__file__).rsplit("/", 1)[0])

# ── Optional fakeredis support ────────────────────────────────────────────────

def _build_fake_redis_factory():
    """
    Return a class whose from_url() hands out async FakeRedis instances that
    all share one in-process FakeServer (so pub/sub messages are propagated).

    Supports fakeredis >= 2.0 (redis-py async API).
    """
    try:
        from fakeredis import FakeServer
        from fakeredis.asyncio import FakeRedis  # fakeredis >= 2.0
    except ImportError as exc:
        print(_c(RED, f"fakeredis not installed: {exc}"))
        print(_c(DIM, "  pip install fakeredis>=2.0"))
        sys.exit(1)

    server = FakeServer()

    class _Factory:
        @classmethod
        def from_url(cls, url: str, **kwargs: Any):
            return FakeRedis(server=server, **kwargs)

    return _Factory

from news_streamer.models.news import (
    Category,
    Sentiment,
    SourceType,
    TaggedNewsItem,
    Urgency,
)
from news_streamer.pubsub.channels import channels_for_item
from news_streamer.pubsub.publisher import NewsPublisher
from pub_sub_feed.subscriber import FeedSubscriber

# ── ANSI colours (degrade gracefully if terminal doesn't support them) ────────

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
DIM = "\033[2m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}"


# ── Sample TaggedNewsItems ────────────────────────────────────────────────────

def _item(
    item_id: str,
    headline: str,
    urgency: Urgency,
    categories: tuple[Category, ...],
    tickers: tuple[str, ...],
    sentiment: Sentiment = Sentiment.NEUTRAL,
    score: float = 0.0,
) -> TaggedNewsItem:
    now = datetime.now(timezone.utc)
    return TaggedNewsItem(
        id=item_id,
        timestamp=now,
        received_at=now,
        headline=headline,
        body="",
        source_type=SourceType.NEWS_WIRE,
        source_handle="smoke-test",
        source_url="",
        tickers=tickers,
        categories=categories,
        keywords=(),
        sentiment=sentiment,
        sentiment_score=score,
        urgency=urgency,
    )


ITEMS: list[TaggedNewsItem] = [
    _item(
        "item-1",
        "Fed cuts rates 50bps — surprise move rattles bond markets",
        Urgency.BREAKING,
        (Category.MACRO,),
        (),
        Sentiment.BEARISH,
        -0.6,
    ),
    _item(
        "item-2",
        "Bitcoin hits $100k for the first time",
        Urgency.BREAKING,
        (Category.CRYPTO,),
        ("BTC",),
        Sentiment.BULLISH,
        0.9,
    ),
    _item(
        "item-3",
        "Apple reports Q4 earnings beat — EPS $1.62 vs $1.55 est.",
        Urgency.HIGH,
        (Category.STOCKS, Category.EARNINGS),
        ("AAPL",),
        Sentiment.BULLISH,
        0.7,
    ),
    _item(
        "item-4",
        "Ethereum Pectra upgrade goes live on mainnet",
        Urgency.NORMAL,
        (Category.CRYPTO,),
        ("ETH",),
        Sentiment.BULLISH,
        0.5,
    ),
    _item(
        "item-5",
        "UN Security Council calls emergency session on Gaza",
        Urgency.NORMAL,
        (Category.GEOPOLITICS,),
        (),
        Sentiment.BEARISH,
        -0.4,
    ),
]

# ── Subscriber configurations ─────────────────────────────────────────────────
#
# name             feeds
# ─────────────────────────────────────────────────────────────────────────────
# ALL_NEWS         news:all
# BREAKING+CRYPTO  news:urgency:breaking  news:category:crypto
# BTC_WATCHER      news:ticker:BTC

SUBSCRIBERS: list[tuple[str, list[str]]] = [
    ("ALL_NEWS",        ["news:all"]),
    ("BREAKING+CRYPTO", ["news:urgency:breaking", "news:category:crypto"]),
    ("BTC_WATCHER",     ["news:ticker:BTC"]),
]

# ── Subscriber task ───────────────────────────────────────────────────────────

async def collect(
    name: str,
    feeds: list[str],
    redis_url: str,
    ready: asyncio.Event,
    stop: asyncio.Event,
) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
    """Connect, signal ready, then collect messages until stop is set."""
    received: list[tuple[str, dict[str, Any]]] = []
    async with FeedSubscriber(feeds=feeds, redis_url=redis_url) as sub:
        ready.set()
        while not stop.is_set():
            result = await sub.pull(timeout=0.1)
            if result is not None:
                received.append(result)
    return name, received


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(redis_url: str, inter_item_delay: float, fake: bool) -> None:
    print()
    print(_c(BOLD, "=== pub/sub integration smoke test ==="))
    mode = "in-process fakeredis" if fake else redis_url
    print(_c(DIM, f"Redis: {mode}"))
    print()

    # -- Print what we're about to publish ------------------------------------
    print(_c(BOLD, "Items to publish:"))
    for item in ITEMS:
        channels = channels_for_item(item)
        ch_str = "  ".join(_c(DIM, c) for c in channels)
        print(f"  [{item.id}] {item.headline[:60]}")
        print(f"         channels: {ch_str}")
    print()

    # -- Print subscriber configs ---------------------------------------------
    print(_c(BOLD, "Subscribers:"))
    for name, feeds in SUBSCRIBERS:
        feeds_str = "  ".join(_c(CYAN, f) for f in feeds)
        print(f"  {_c(BOLD, name):<22}  feeds: {feeds_str}")
    print()

    # -- Start subscriber tasks -----------------------------------------------
    ready_events = [asyncio.Event() for _ in SUBSCRIBERS]
    stop_event = asyncio.Event()

    sub_tasks = [
        asyncio.create_task(
            collect(name, feeds, redis_url, ready_events[i], stop_event)
        )
        for i, (name, feeds) in enumerate(SUBSCRIBERS)
    ]

    # Wait until every subscriber has registered its subscription with Redis
    await asyncio.gather(*(e.wait() for e in ready_events))
    print(_c(GREEN, "All subscribers connected and subscribed."))
    print()

    # -- Publish items --------------------------------------------------------
    print(_c(BOLD, "Publishing:"))
    async with NewsPublisher(redis_url=redis_url) as pub:
        for item in ITEMS:
            deliveries = await pub.publish(item)
            print(
                f"  {_c(CYAN, item.id)}  {item.headline[:55]:<56}"
                f"  → {deliveries} delivery(s)"
            )
            await asyncio.sleep(inter_item_delay)

    print()

    # Give subscribers a short window to drain any in-flight messages
    await asyncio.sleep(0.3)
    stop_event.set()

    results: list[tuple[str, list[tuple[str, dict]]]] = await asyncio.gather(*sub_tasks)

    # -- Print results --------------------------------------------------------
    print(_c(BOLD, "Results:"))
    print()

    for sub_name, received in results:
        print(_c(BOLD, f"  {sub_name}") + _c(DIM, f"  ({len(received)} message(s))"))
        if not received:
            print(_c(DIM, "    (nothing received)"))
        else:
            for channel, data in received:
                item_id = data.get("id", "?")
                headline = data.get("headline", "")[:55]
                urgency = data.get("urgency", "")
                print(
                    f"    {_c(CYAN, channel):<42}"
                    f"  [{item_id}] {headline}"
                    f"  {_c(YELLOW, urgency)}"
                )
        print()

    # -- Summary table --------------------------------------------------------
    item_ids = [item.id for item in ITEMS]
    sub_names = [name for name, _ in results]

    col_w = 14
    header = f"  {'':25}" + "".join(f"{sid:>{col_w}}" for sid in sub_names)
    print(_c(BOLD, "Delivery matrix")
          + _c(DIM, "  (# times each subscriber received each item):"))
    print(_c(DIM, header))

    for item_id in item_ids:
        row = f"  {item_id:<25}"
        for _, received in results:
            count = sum(1 for ch, d in received if d.get("id") == item_id)
            cell = str(count) if count else _c(DIM, ".")
            row += f"{cell:>{col_w}}"
        print(row)

    print()
    print(_c(GREEN, _c(BOLD, "Done.")))
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

async def _run(redis_url: str, inter_item_delay: float, fake: bool) -> None:
    """Wrap main() with optional fakeredis patches."""
    if fake:
        factory = _build_fake_redis_factory()
        with (
            patch("pub_sub_feed.publisher.Redis", factory),
            patch("pub_sub_feed.subscriber.Redis", factory),
        ):
            await main(redis_url=redis_url, inter_item_delay=inter_item_delay, fake=True)
    else:
        await main(redis_url=redis_url, inter_item_delay=inter_item_delay, fake=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis connection URL (default: redis://localhost:6379/0)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        metavar="SECS",
        help="Delay between published items in seconds (default: 0.05)",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use in-process fakeredis instead of a live Redis server",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_run(
            redis_url=args.redis_url,
            inter_item_delay=args.delay,
            fake=args.fake,
        ))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(_c(RED, f"\nFailed: {exc}"))
        if not args.fake:
            print(_c(DIM, "Tip: run with --fake for zero-dependency mode, or start Redis with:"))
            print(_c(DIM, "     podman run --rm -p 6379:6379 redis"))
        sys.exit(1)
