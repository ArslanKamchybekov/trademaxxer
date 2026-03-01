"""
Groq Prompt Templates

Versioned prompts for market classification. Every Decision records the
PROMPT_VERSION that produced it so results are traceable.
"""
from __future__ import annotations

PROMPT_VERSION = "v6"

SYSTEM_PROMPT = (
    "You reprice prediction-market contracts based on breaking news.\n"
    "MOST NEWS IS IRRELEVANT TO MOST CONTRACTS. "
    "Only move the price if the headline has a DIRECT causal link to the contract outcome. "
    "If there is no clear connection, return p = current price EXACTLY.\n\n"
    "Examples of IRRELEVANT (return current price):\n"
    '- "Oil spikes" on contract "Will it snow in NYC?" → p=current\n'
    '- "Fed raises rates" on contract "Will Team X win?" → p=current\n'
    '- Vague or tangential geopolitical news on unrelated contracts → p=current\n\n'
    'JSON only: {"action":"YES"|"NO","p":<int 1-99>}\n'
    "YES = news pushes contract price UP (p > current).\n"
    "NO = news pushes contract price DOWN (p < current).\n"
    "p = your fair price in cents AFTER this news. "
    "Return current price exactly if unsure or unrelated."
)


def build_user_prompt(
    headline: str,
    body: str,
    question: str,
    current_probability: float,
    rules_primary: str = "",
) -> str:
    price_cents = round(current_probability * 100)
    parts = [headline]
    body_trimmed = body.strip()
    if body_trimmed:
        parts.append(body_trimmed[:280])
    parts.append(f"Contract: {question}")
    if rules_primary:
        parts.append(f"Resolution: {rules_primary[:300]}")
    parts.append(f"Current price: {price_cents}¢")
    return "\n".join(parts)
