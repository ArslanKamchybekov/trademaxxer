"""
Local ONNX NLI inference — same model as Modal, zero network overhead.

Downloads the model from HuggingFace on first run, then caches locally.
Runs on CPU via ONNX Runtime. Same interface as FastMarketAgent.evaluate_batch().

Usage:
    from agents.local_inference import LocalNLIAgent
    agent = LocalNLIAgent()
    results = agent.evaluate_batch([
        {"headline": "...", "question": "...", "probability": 0.5,
         "market_address": "...", "story_id": "..."},
    ])
"""
from __future__ import annotations

import time

import numpy as np
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer

from agents.nli_postprocess import postprocess_logits

ONNX_REPO = "Xenova/nli-deberta-v3-xsmall"
ONNX_FILE = "onnx/model.onnx"
TOKENIZER_NAME = "cross-encoder/nli-deberta-v3-xsmall"


class LocalNLIAgent:
    """In-process ONNX NLI agent. Same logic as the Modal FastMarketAgent."""

    def __init__(self) -> None:
        import onnxruntime as ort

        model_path = hf_hub_download(ONNX_REPO, ONNX_FILE)
        self.session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        self.tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)

    def evaluate_batch(self, items: list[dict]) -> list[dict]:
        t0 = time.monotonic()

        premises = [item["headline"] for item in items]
        hypotheses = [item["question"] for item in items]

        tokens = self.tokenizer(
            premises,
            hypotheses,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="np",
        )

        logits = self.session.run(
            None,
            {
                "input_ids": tokens["input_ids"],
                "attention_mask": tokens["attention_mask"],
            },
        )[0]

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
                "prompt_version": "nli-v1-local",
            })

        return results
