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

SKIP_THRESHOLD = 0.03


async def evaluate(
    story: StoryPayload,
    market: MarketConfig,
    groq: GroqClient,
) -> Decision:
    """
    Classify a single (story, market) pair via Groq.

    Groq returns YES/NO + theo. If |theo - current| < SKIP_THRESHOLD
    the action is overridden to SKIP. Confidence is derived from the delta.
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

    theo = result.get("theo")
    if theo is not None:
        theo = round(max(0.01, min(0.99, float(theo))), 3)

    delta = abs(theo - market.current_probability) if theo is not None else 0.0
    action = result["action"] if delta >= SKIP_THRESHOLD else "SKIP"
    confidence = round(min(delta * 2.0, 1.0), 3)

    decision = Decision(
        action=action,
        confidence=confidence,
        reasoning="",
        market_address=market.address,
        story_id=story.id,
        latency_ms=round(latency_ms, 1),
        prompt_version=PROMPT_VERSION,
        theo=theo,
    )

    if action != "SKIP":
        logger.info(
            f"[{action}] {market.question[:50]} "
            f"theo={theo:.0%} Δ={delta:+.0%} {latency_ms:.0f}ms"
        )

    return decision
