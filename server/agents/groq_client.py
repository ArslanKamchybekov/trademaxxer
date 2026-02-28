"""
Groq API Client

Thin async wrapper around the Groq Python SDK. Handles retries on transient
errors, enforces a hard timeout, and parses the JSON response.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

MODEL = "llama-3.1-8b-instant"
MAX_RETRIES = 1
TIMEOUT_S = 2.0
TEMPERATURE = 0.1
MAX_TOKENS = 32


class GroqClassificationError(Exception):
    """Raised when Groq fails to return a valid classification."""

    pass


def _normalize_action(raw: str) -> str | None:
    """
    Extract YES / NO / SKIP from the action field, even if the model
    returned something verbose like "MORE likely to resolve YES".
    """
    if not raw:
        return None
    upper = raw.strip().upper()
    if upper in ("YES", "NO", "SKIP"):
        return upper
    if "YES" in upper and "NO" not in upper:
        return "YES"
    if "NO" in upper and "YES" not in upper:
        return "NO"
    if "SKIP" in upper or "IRRELEVANT" in upper or "AMBIGUOUS" in upper:
        return "SKIP"
    return None


class GroqClient:
    """
    Async Groq chat-completion client for agent classification.

    Initialise once per container (in @modal.enter) and reuse across calls.
    Reads GROQ_API_KEY from the environment automatically.
    """

    def __init__(self, api_key: str | None = None) -> None:
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=api_key)

    async def classify(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """
        Send a classification request to Groq and return parsed JSON.

        Retries once on transient errors (rate-limit, timeout, 5xx).
        Raises GroqClassificationError on permanent failure or malformed output.
        """
        from groq import (
            APIStatusError,
            APITimeoutError,
            RateLimitError,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None

        for attempt in range(1 + MAX_RETRIES):
            try:
                t0 = time.monotonic()

                completion = await self._client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_completion_tokens=MAX_TOKENS,
                    response_format={"type": "json_object"},
                    stream=False,
                    timeout=TIMEOUT_S,
                )

                elapsed_ms = (time.monotonic() - t0) * 1000
                raw = completion.choices[0].message.content

                if not raw:
                    raise GroqClassificationError("Empty response from Groq")

                parsed = json.loads(raw)

                action = _normalize_action(parsed.get("action", ""))
                if action is None:
                    raise GroqClassificationError(
                        f"Could not parse action from Groq response: "
                        f"{parsed.get('action')!r}"
                    )

                raw_p = parsed.get("p") or parsed.get("theo")
                if raw_p is not None:
                    p = float(raw_p)
                    theo = max(0.01, min(0.99, p / 100.0 if p > 1.0 else p))
                else:
                    theo = None

                return {
                    "action": action,
                    "theo": theo,
                    "_latency_ms": elapsed_ms,
                }

            except (RateLimitError, APITimeoutError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"Groq transient error (attempt {attempt + 1}), retrying: {e}"
                    )
                    continue
            except APIStatusError as e:
                if e.status_code >= 500 and attempt < MAX_RETRIES:
                    last_error = e
                    logger.warning(
                        f"Groq 5xx error (attempt {attempt + 1}), retrying: {e}"
                    )
                    continue
                raise GroqClassificationError(
                    f"Groq API error {e.status_code}: {e}"
                ) from e
            except json.JSONDecodeError as e:
                raise GroqClassificationError(
                    f"Groq returned invalid JSON: {e}"
                ) from e

        raise GroqClassificationError(
            f"Groq failed after {1 + MAX_RETRIES} attempts: {last_error}"
        )
