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

MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 1
TIMEOUT_S = 2.0
TEMPERATURE = 0.2
MAX_TOKENS = 256


class GroqClassificationError(Exception):
    """Raised when Groq fails to return a valid classification."""

    pass


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

                action = parsed.get("action")
                if action not in ("YES", "NO", "SKIP"):
                    raise GroqClassificationError(
                        f"Invalid action {action!r} in Groq response"
                    )

                parsed.setdefault("confidence", 0.5)
                parsed.setdefault("reasoning", "")
                parsed["_latency_ms"] = elapsed_ms

                return parsed

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
