"""
Modal Deployment — MarketAgent

Serverless Groq classification deployed on Modal. Each container initialises
a GroqClient once on cold start, then handles up to 20 concurrent evaluations
(I/O-bound Groq API calls).

Deploy:
    cd server
    modal deploy agents/modal_app.py

Invoke from VPS:
    import modal
    AgentCls = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")
    agent = AgentCls()
    result = await agent.evaluate.remote.aio(story_dict, market_dict)
"""
from __future__ import annotations

import modal

app = modal.App("trademaxxer-agents")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("groq")
    .add_local_python_source("agents")
)


@app.cls(
    image=image,
    secrets=[modal.Secret.from_name("groq-api-key")],
    scaledown_window=120,
)
@modal.concurrent(max_inputs=20)
class MarketAgent:
    """
    Serverless agent that classifies a news story against a prediction market.

    Container lifecycle:
        - @modal.enter: init GroqClient (once per cold start)
        - evaluate(): called per (story, market) pair, returns Decision dict
        - Container stays warm for 120s, then scales to zero
    """

    @modal.enter()
    def init(self) -> None:
        from agents.groq_client import GroqClient

        self.groq = GroqClient()

    @modal.method()
    async def evaluate(self, story_dict: dict, market_dict: dict) -> dict:
        """
        Classify a story against a market.

        Accepts and returns plain dicts (Modal serialisation boundary).
        Deserialises to dataclasses internally, calls agent_logic.evaluate,
        then serialises the Decision back to a dict.
        """
        from agents.agent_logic import evaluate as _evaluate
        from agents.schemas import MarketConfig, StoryPayload

        story = StoryPayload.from_dict(story_dict)
        market = MarketConfig.from_dict(market_dict)

        decision = await _evaluate(story, market, self.groq)
        return decision.to_dict()
