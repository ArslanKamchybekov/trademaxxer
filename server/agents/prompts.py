"""
Groq Prompt Templates

Versioned prompts for market classification. Every Decision records the
PROMPT_VERSION that produced it so results are traceable.
"""
from __future__ import annotations

PROMPT_VERSION = "v5"

SYSTEM_PROMPT = (
    "You price prediction-market contracts. "
    "A contract trades at a given price (0-99¢). "
    "Given breaking news, output where the contract SHOULD trade now.\n"
    'JSON only: {"action":"YES"|"NO","p":<int 1-99>}\n'
    "action=YES if news pushes price up, NO if down. "
    "p=your fair price in cents after this news. "
    "If news is irrelevant, p=current price."
)


def build_user_prompt(
    headline: str,
    body: str,
    question: str,
    current_probability: float,
) -> str:
    price_cents = round(current_probability * 100)
    parts = [headline]
    body_trimmed = body.strip()
    if body_trimmed:
        parts.append(body_trimmed[:200])
    parts.append(f"Contract: {question}")
    parts.append(f"Price: {price_cents}¢")
    return "\n".join(parts)
