"""
In-Memory Pub/Sub Bus

Zero-copy, zero-serialization async pub/sub with channel-based routing.
Subscribers register on named channels; publish() fans out to all matching
callbacks in O(channels) with no network hop.

    bus = PubSub()
    bus.subscribe("politics", my_callback)
    await bus.publish(["politics", "crypto"], story)  # fires my_callback once
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

Callback = Callable[[Any], Awaitable[None]]


class PubSub:
    """
    In-memory async pub/sub with per-channel subscriber lists.

    - subscribe/unsubscribe are O(1) dict ops.
    - publish fans out to the union of subscribers across all given channels,
      deduped so each callback fires at most once per publish.
    - Callbacks are fired as concurrent tasks (non-blocking).
    """

    __slots__ = ("_subs",)

    def __init__(self) -> None:
        self._subs: dict[str, list[Callback]] = defaultdict(list)

    def subscribe(self, channel: str, cb: Callback) -> None:
        self._subs[channel].append(cb)

    def unsubscribe(self, channel: str, cb: Callback) -> None:
        try:
            self._subs[channel].remove(cb)
            if not self._subs[channel]:
                del self._subs[channel]
        except (ValueError, KeyError):
            pass

    async def publish(self, channels: list[str] | tuple[str, ...], payload: Any) -> int:
        """
        Fan out payload to all subscribers on any of the given channels.

        Each callback is invoked at most once even if it appears on multiple
        channels. Returns the number of unique callbacks fired.
        """
        seen: set[int] = set()
        tasks: list[asyncio.Task] = []

        for ch in channels:
            for cb in self._subs.get(ch, ()):
                cb_id = id(cb)
                if cb_id in seen:
                    continue
                seen.add(cb_id)
                tasks.append(asyncio.create_task(cb(payload)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return len(tasks)

    @property
    def channel_count(self) -> int:
        return len(self._subs)

    @property
    def subscriber_count(self) -> int:
        return sum(len(cbs) for cbs in self._subs.values())
