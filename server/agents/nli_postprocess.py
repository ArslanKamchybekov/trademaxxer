"""
NLI Postprocessor

Maps DeBERTa NLI logits to Decision-compatible (action, confidence, reasoning).
Label ordering for cross-encoder/nli-deberta-v3-xsmall:
  0 = contradiction  → NO
  1 = entailment     → YES
  2 = neutral        → SKIP
"""
from __future__ import annotations

import numpy as np

NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"
LABEL_MAP = {0: "NO", 1: "YES", 2: "SKIP"}

REASONING_TEMPLATES = {
    "YES": "NLI entailment — headline supports market thesis",
    "NO": "NLI contradiction — headline opposes market thesis",
    "SKIP": "NLI neutral — headline unrelated to market",
}


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def postprocess_logits(
    logits: np.ndarray,
    current_probability: float,
) -> tuple[str, float, str]:
    """
    Convert raw NLI logits to (action, confidence, reasoning).

    Confidence is scaled by how much the signal moves the market:
    - YES at 95% prob → already priced in → lower confidence
    - NO at 10% prob → already priced in → lower confidence
    """
    probs = softmax(logits)
    action_idx = int(np.argmax(probs))
    action = LABEL_MAP[action_idx]
    raw_conf = float(probs[action_idx])

    if action == "YES":
        confidence = raw_conf * (1.0 - current_probability)
    elif action == "NO":
        confidence = raw_conf * current_probability
    else:
        confidence = raw_conf * 0.5

    confidence = round(min(max(confidence, 0.0), 1.0), 3)
    reasoning = REASONING_TEMPLATES[action]

    return action, confidence, reasoning
