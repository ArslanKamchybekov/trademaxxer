"""
Agent Pipeline Data Models

Schemas for data flowing between the dispatcher, Modal agents, and decision queue.
All models use frozen dataclasses with __post_init__ validation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Market configuration — one per on-chain prediction market
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarketConfig:
    """
    Describes a single prediction market that an agent evaluates against.

    The agent receives this alongside a news story and decides whether the
    news supports YES, NO, or is irrelevant (SKIP) for the market question.
    """

    address: str
    question: str
    current_probability: float
    tags: tuple[str, ...]
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("address must be non-empty")
        if not self.question:
            raise ValueError("question must be non-empty")
        if not (0.0 <= self.current_probability <= 1.0):
            raise ValueError(
                f"current_probability must be in [0.0, 1.0], got {self.current_probability}"
            )
        if not self.tags:
            raise ValueError("tags must contain at least one tag")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.expires_at is not None:
            d["expires_at"] = self.expires_at.isoformat()
        else:
            d["expires_at"] = None
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MarketConfig:
        expires = d.get("expires_at")
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        return cls(
            address=d["address"],
            question=d["question"],
            current_probability=d["current_probability"],
            tags=tuple(d["tags"]),
            expires_at=expires,
        )


# ---------------------------------------------------------------------------
# Story payload — slimmed-down news item sent to Modal agents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StoryPayload:
    """
    Lightweight news payload for agent evaluation.

    Stripped from TaggedNewsItem to only the fields the agent needs,
    keeping the Modal function's input small and serializable.
    """

    id: str
    headline: str
    body: str
    tags: tuple[str, ...]
    source: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id must be non-empty")
        if not self.headline:
            raise ValueError("headline must be non-empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StoryPayload:
        ts = d["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            id=d["id"],
            headline=d["headline"],
            body=d.get("body", ""),
            tags=tuple(d.get("tags", ())),
            source=d.get("source", ""),
            timestamp=ts,
        )


# ---------------------------------------------------------------------------
# Decision — output from Groq classification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    """
    Agent's classification of a news story against a specific market.

    Produced by agent_logic.evaluate(), consumed by the dispatcher
    which writes it to the decisions:raw stream.
    """

    action: Literal["YES", "NO", "SKIP"]
    confidence: float
    reasoning: str
    market_address: str
    story_id: str
    latency_ms: float
    prompt_version: str

    def __post_init__(self) -> None:
        if self.action not in ("YES", "NO", "SKIP"):
            raise ValueError(f"action must be YES, NO, or SKIP — got {self.action!r}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )
        if not self.market_address:
            raise ValueError("market_address must be non-empty")
        if not self.story_id:
            raise ValueError("story_id must be non-empty")
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {self.latency_ms}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Decision:
        return cls(
            action=d["action"],
            confidence=d["confidence"],
            reasoning=d.get("reasoning", ""),
            market_address=d["market_address"],
            story_id=d["story_id"],
            latency_ms=d.get("latency_ms", 0.0),
            prompt_version=d.get("prompt_version", "unknown"),
        )
