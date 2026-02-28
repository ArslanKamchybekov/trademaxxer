"""
Agent Core Logic

Pure evaluation function with zero Modal dependency — fully unit-testable.
Takes a story + market + groq client, returns a Decision.
"""
from __future__ import annotations

import logging
import time

from agents.groq_client import GroqClassificationError, GroqClient
from agents.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from agents.schemas import Decision, MarketConfig, StoryPayload

logger = logging.getLogger(__name__)


async def evaluate(
    story: StoryPayload,
    market: MarketConfig,
    groq: GroqClient,
) -> Decision:
    """
    Classify a single (story, market) pair via Groq.

    Returns a Decision with action, confidence, reasoning, and timing metadata.
    Raises GroqClassificationError on unrecoverable failure.
    """
    user_prompt = build_user_prompt(
        headline=story.headline,
        body=story.body,
        question=market.question,
        current_probability=market.current_probability,
    )

    t0 = time.monotonic()
    result = await groq.classify(SYSTEM_PROMPT, user_prompt)
    fallback_latency = (time.monotonic() - t0) * 1000

    latency_ms = result.get("_latency_ms", fallback_latency)

    confidence = result.get("confidence", 0.5)
    confidence = max(0.0, min(1.0, float(confidence)))

    decision = Decision(
        action=result["action"],
        confidence=confidence,
        reasoning=result.get("reasoning", ""),
        market_address=market.address,
        story_id=story.id,
        latency_ms=round(latency_ms, 1),
        prompt_version=PROMPT_VERSION,
    )

    logger.info(
        f"[{decision.action}] {market.question[:60]} "
        f"(conf={decision.confidence:.2f}, {decision.latency_ms:.0f}ms)"
    )

    return decision
