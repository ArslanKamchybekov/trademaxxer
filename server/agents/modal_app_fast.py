"""
Modal Deployment — FastMarketAgent (NLI + ONNX)

Serverless NLI-based classification on Modal using ONNX Runtime.
Loads the pre-exported Xenova/nli-deberta-v3-xsmall ONNX model directly
from HuggingFace — no PyTorch, no manual export, no secrets.

Image is ~300MB (vs ~1.5GB with torch). Cold starts are fast.
Batched endpoint: one RPC evaluates up to 50 markets per story.

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

ONNX_REPO = "Xenova/nli-deberta-v3-xsmall"
ONNX_FILE = "onnx/model.onnx"
TOKENIZER_NAME = "cross-encoder/nli-deberta-v3-xsmall"

app = modal.App("trademaxxer-agents-fast")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("onnxruntime", "transformers", "numpy", "huggingface_hub")
    .run_commands(
        "python -c \""
        "from huggingface_hub import hf_hub_download; "
        f"hf_hub_download('{ONNX_REPO}', '{ONNX_FILE}'); "
        "from transformers import AutoTokenizer; "
        f"AutoTokenizer.from_pretrained('{TOKENIZER_NAME}')"
        "\""
    )
    .add_local_python_source("agents")
)


@app.cls(image=image, scaledown_window=300, buffer_containers=1)
class FastMarketAgent:
    """
    ONNX NLI agent. Classifies (headline, market_question) pairs via
    entailment/contradiction/neutral -> YES/NO/SKIP.

    Container lifecycle:
        - @modal.enter: load ONNX model + tokenizer from cache (baked in image)
        - evaluate_batch(): batched inference, returns list of Decision dicts
        - Container stays warm for 5min, then scales to zero
    """

    @modal.enter()
    def init(self) -> None:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from transformers import AutoTokenizer

        model_path = hf_hub_download(ONNX_REPO, ONNX_FILE)
        self.session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        self.tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)

    @modal.method()
    def evaluate_batch(self, items: list[dict]) -> list[dict]:
        """
        Evaluate a batch of (headline, market_question) pairs.

        Each item: {"headline", "question", "probability", "market_address", "story_id"}
        Returns: list of Decision-compatible dicts.
        """
        import time

        import numpy as np

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
                "prompt_version": "nli-v1",
            })

        return results
