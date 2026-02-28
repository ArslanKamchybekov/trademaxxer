"""
Groq Prompt Templates

Versioned prompts for market classification. Every Decision records the
PROMPT_VERSION that produced it so results are traceable.
"""
from __future__ import annotations

PROMPT_VERSION = "v3"

# ---------------------------------------------------------------------------
# System prompt — sets the role and constrains output format
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    'Prediction-market bot. Output JSON only:\n'
    '{"action":"YES"|"NO"|"SKIP","confidence":0.0-1.0,"reasoning":"<short>"}\n'
    "YES=news supports yes, NO=news supports no, SKIP=irrelevant. "
    "Factor in current probability. If unsure, SKIP."
)

# ---------------------------------------------------------------------------
# User prompt — filled per (story, market) pair
# ---------------------------------------------------------------------------


def build_user_prompt(
    headline: str,
    body: str,
    question: str,
    current_probability: float,
) -> str:
    """
    Build the user-turn message for a single (story, market) evaluation.

    Keeps the prompt compact — Groq latency scales with token count.
    """
    parts = [f"Headline: {headline}"]

    body_trimmed = body.strip()
    if body_trimmed:
        if len(body_trimmed) > 300:
            body_trimmed = body_trimmed[:300] + "…"
        parts.append(f"Body: {body_trimmed}")

    parts.append(f"Market: {question}")
    parts.append(f"Prob(YES): {current_probability:.0%}")

    return "\n".join(parts)
