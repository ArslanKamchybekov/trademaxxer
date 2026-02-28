"""
Modal Deployment — FastMarketAgent (NLI)

Serverless NLI-based classification on Modal. Loads a pretrained
cross-encoder/nli-deberta-v3-xsmall model directly from HuggingFace.
No Groq API, no secrets, no network calls from inside the container.

The model is baked into the image so cold starts don't include a download.
Batched endpoint: one RPC evaluates all markets for a single story.

Deploy:
    cd server
    modal deploy agents/modal_app_fast.py

Invoke from VPS:
    import modal
    Cls = modal.Cls.from_name("trademaxxer-agents-fast", "FastMarketAgent")
    agent = Cls()
    results = await agent.evaluate_batch.remote.aio([
        {"headline": "...", "question": "...", "probability": 0.5,
         "market_address": "...", "story_id": "..."},
    ])
"""
from __future__ import annotations

import modal

MODEL_NAME = "cross-encoder/nli-deberta-v3-xsmall"

app = modal.App("trademaxxer-agents-fast")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("transformers", "torch", "numpy")
    .run_commands(
        f"python -c \""
        f"from transformers import AutoTokenizer, AutoModelForSequenceClassification; "
        f"AutoTokenizer.from_pretrained('{MODEL_NAME}'); "
        f"AutoModelForSequenceClassification.from_pretrained('{MODEL_NAME}')"
        f"\""
    )
    .add_local_python_source("agents")
)


@app.cls(image=image, scaledown_window=300, buffer_containers=1)
class FastMarketAgent:
    """
    NLI-based agent. Classifies (headline, market_question) pairs via
    entailment/contradiction/neutral → YES/NO/SKIP.

    Container lifecycle:
        - @modal.enter: load model + tokenizer from cache (instant, baked in image)
        - evaluate_batch(): batched inference, returns list of Decision dicts
        - Container stays warm for 5min, then scales to zero
    """

    @modal.enter()
    def init(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.device = "cpu"

    @modal.method()
    def evaluate_batch(self, items: list[dict]) -> list[dict]:
        """
        Evaluate a batch of (headline, market_question) pairs.

        Each item: {"headline", "question", "probability", "market_address", "story_id"}
        Returns: list of Decision-compatible dicts.
        """
        import time

        import numpy as np
        import torch

        from agents.nli_postprocess import postprocess_logits

        t0 = time.monotonic()

        premises = [item["headline"] for item in items]
        hypotheses = [item["question"] for item in items]

        tokens = self.tokenizer(
            premises,
            hypotheses,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )

        with torch.no_grad():
            outputs = self.model(**tokens)
            logits = outputs.logits.numpy()

        inference_ms = (time.monotonic() - t0) * 1000

        results = []
        for i, item in enumerate(items):
            action, confidence, reasoning = postprocess_logits(
                logits[i], item["probability"]
            )
            results.append({
                "action": action,
                "confidence": confidence,
                "reasoning": reasoning,
                "market_address": item["market_address"],
                "story_id": item["story_id"],
                "latency_ms": round(inference_ms, 1),
                "prompt_version": "nli-v1",
            })

        return results
