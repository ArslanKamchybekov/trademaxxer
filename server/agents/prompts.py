"""
Groq Prompt Templates

Versioned prompts for market classification. Every Decision records the
PROMPT_VERSION that produced it so results are traceable.
"""
from __future__ import annotations

PROMPT_VERSION = "v1"

# ---------------------------------------------------------------------------
# System prompt — sets the role and constrains output format
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a prediction-market analyst. You will receive a breaking news "
    "headline (and optional body) together with a prediction market question "
    "and its current implied probability.\n"
    "\n"
    "Your job:\n"
    "1. Decide whether this news makes the market question MORE likely to "
    "resolve YES, MORE likely to resolve NO, or is irrelevant (SKIP).\n"
    "2. Rate your confidence from 0.0 (pure guess) to 1.0 (certain).\n"
    "3. Give a one-sentence reasoning.\n"
    "\n"
    "Rules:\n"
    "- ONLY output valid JSON. No markdown, no commentary.\n"
    "- Use exactly this schema:\n"
    '  {"action": "YES" | "NO" | "SKIP", "confidence": <float 0.0-1.0>, '
    '"reasoning": "<one sentence>"}\n'
    "- If the news is ambiguous or unrelated, choose SKIP.\n"
    "- Consider the current probability — a market already at 0.95 needs "
    "very strong counter-evidence to flip.\n"
    "- Speed matters more than nuance. Be decisive."
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
    parts = [f"**Headline:** {headline}"]

    body_trimmed = body.strip()
    if body_trimmed:
        if len(body_trimmed) > 500:
            body_trimmed = body_trimmed[:500] + "…"
        parts.append(f"**Body:** {body_trimmed}")

    parts.append(f"**Market question:** {question}")
    parts.append(f"**Current probability (YES):** {current_probability:.0%}")

    return "\n".join(parts)
