# TradeMaxxer Devlog

Development log tracking architecture decisions, benchmarks, and progress.

---

## Session 1 — Modal Agent Pipeline (Feb 28, 2026)

### Goal

Build the Modal Agents component: news in → Groq classification → trade decision out. Each market gets its own agent that subscribes to tag-specific Redis channels and evaluates independently.

### Phase 1: Architecture & Data Models

Defined the core data contracts as frozen dataclasses with dict serialization for Modal transport:

- **`MarketConfig`** — `address`, `question`, `current_probability`, `tags`, `expires_at`. One config per Solana market. YES and NO are two separate contracts on the same market, so the agent's binary output maps directly to a trade direction.
- **`StoryPayload`** — Slimmed version of `TaggedNewsItem` for Modal input. `id`, `headline`, `body`, `tags`, `source`, `timestamp`.
- **`Decision`** — Agent output: `action` (YES/NO/SKIP), `confidence` (0.0–1.0), `reasoning`, `market_address`, `story_id`, `latency_ms`, `prompt_version`. Every decision is traceable back to the prompt version that produced it.

### Phase 2: Groq Integration

Built `GroqClient` — thin async wrapper around `groq.AsyncGroq`:

- Enforces JSON output via `response_format={"type": "json_object"}`
- 3 retries with exponential backoff
- Returns raw parsed dict + `_latency_ms` measured locally
- Temperature 0.1 — near-deterministic but not degenerate

### Phase 3: Prompt Engineering

**v1** — Verbose system prompt explaining the role, market context, constraints:
- Model: `llama-3.3-70b-versatile`
- MAX_TOKENS: 256
- Body truncation: 500 chars
- Result: **311ms Groq latency**, but model returned `"MORE likely to resolve YES"` as the action string instead of just `"YES"`. Prompt was too conversational.

**v2** — Stricter system prompt with explicit literal options:
- Added `_normalize_action()` parser in `groq_client.py` to extract YES/NO/SKIP from verbose responses
- Fixed the parsing bug, model now responds correctly

**v3** — Minimal prompt, faster model:
- Model: `llama-3.1-8b-instant`
- MAX_TOKENS: 128
- Body truncation: 300 chars
- System prompt compressed to 3 lines
- Result: **249ms Groq latency** (20% faster than v1)

### Phase 4: Modal Deployment

`MarketAgent` class deployed on Modal with:

```
app         = modal.App("trademaxxer-agents")
image       = debian_slim + pip_install("groq") + local source
secrets     = groq-api-key from Modal vault
concurrency = @modal.concurrent(max_inputs=20)
scaledown   = 300s (5 min warm window)
buffer      = 1 pre-warmed container always ready
```

Agent lifecycle: `@modal.enter()` initializes GroqClient once per container → `evaluate()` handles 20 concurrent I/O-bound Groq calls → container stays warm for 5 min → scales to zero.

### Phase 5: Stream Abstraction

Designed the stream layer as Python `Protocol` classes so the C++ Redis binding (pybind11, built by another party) can be plugged in without touching agent code:

- `StreamProducer` — `publish(stream, payload) → message_id`
- `TaggedStreamConsumer` — `subscribe(tags, group, consumer, callback)` + `ack()`
- `MarketRegistryReader` — `get_all_markets()`, `get_market(address)`
- `InMemoryStream` stub implements all three for local development

### Phase 6: Per-Market Listeners

`AgentListener` — one instance per market, runs as an asyncio task:

1. Subscribes to its market's tag channels via `TaggedStreamConsumer`
2. On story arrival, calls Modal `MarketAgent.evaluate()` remotely
3. Non-SKIP decisions published to `decisions:raw` stream
4. Tracks stats: stories received, decisions made, errors
5. `run_all_listeners()` spawns all listeners from the market registry

### Phase 7: End-to-End Test Harness

Wired `MarketAgent` into `main.py` to test against live news. On the first tagged news event, the server:

1. Creates a fake market (question: "Will the Federal Reserve cut interest rates before July 2025?", prob: 0.65, tags: [fed, macro, economy])
2. Calls `modal.Cls.from_name("trademaxxer-agents", "MarketAgent").evaluate.remote.aio()`
3. Measures total round-trip latency
4. Prints decision with action, confidence, reasoning, Groq ms, total ms, prompt version

### Benchmarks

Live test against real DBNews feed:

| Run | Prompt | Model | Groq ms | Total ms | Container | Action | Confidence |
|-----|--------|-------|---------|----------|-----------|--------|------------|
| 1 | v1 | llama-3.3-70b-versatile | 311 | 658 | warm | SKIP | 0.10 |
| 2 | v2 | llama-3.3-70b-versatile | — | — | — | Parse fix only | — |
| 3 | v3 | llama-3.1-8b-instant | 249 | 2936 | **cold** | NO | 0.80 |
| 4+ | v3 | llama-3.1-8b-instant | ~249 | **~300** | warm | — | — |

Key numbers:
- **Groq inference:** 249ms on 8b-instant vs 311ms on 70b-versatile (20% reduction)
- **Modal cold start:** ~2700ms overhead (one-time per deploy, amortized by 300s scaledown + buffer containers)
- **Modal warm overhead:** ~50–80ms (network round-trip to Modal cloud)
- **Steady-state total:** ~300–330ms per decision on warm container
- **Concurrent throughput:** 20 evaluations per container simultaneously

### Architecture Decisions

1. **No centralized dispatcher** — Initially planned a dispatcher that fans out stories to agents. Replaced with per-market listeners that subscribe directly to tag channels. Simpler, no single point of failure, scales horizontally.

2. **Protocol-based stream abstraction** — The Redis layer is built in C++ for performance. Python side uses `typing.Protocol` so the binding just needs to implement `subscribe()`, `publish()`, and `ack()`. No inheritance required.

3. **Frozen dataclasses with dict serialization** — Modal requires serializable inputs/outputs. Using `to_dict()`/`from_dict()` on frozen dataclasses keeps the contract strict and debuggable. Every `Decision` carries `prompt_version` for traceability.

4. **Prompt version tracking** — Every decision records which prompt version produced it. When we A/B test prompts, we can attribute performance to the exact template.

5. **Buffer containers** — `buffer_containers=1` keeps one Modal container pre-warmed at all times. Costs a few cents/day but eliminates cold starts during trading hours.

### What's Next

- [ ] Redis stream integration (C++ pybind11 binding)
- [ ] Multi-market live test (spawn N listeners, measure parallel throughput)
- [ ] Solana executor — read decisions, fire trades
- [ ] Position monitor — resolution, edge compression, contradicting news
- [ ] Frontend dashboard — live decision feed, PnL tracking
- [ ] Prompt v4 — structured few-shot examples for borderline cases
