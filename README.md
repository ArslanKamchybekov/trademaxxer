# TradeMaxxer

Autonomous news-to-trade pipeline on Solana. Ingests real-time news, classifies it with Groq via Modal serverless, and executes trades on-chain — all in under one second, with no human in the loop.

## Architecture

```
NEWS FEED ──→ INTAKE SERVICE ──→ REDIS STREAM ──→ MODAL (Groq) ──→ DECISION QUEUE ──→ SOLANA EXECUTOR ──→ POSITION MONITOR
```

### Components

| # | Component | What it does | Runtime |
|---|-----------|-------------|---------|
| 1 | **News Feed** | WebSocket connection to DBNews provider (~2 stories/sec, spikes during major events) | Always-on Python process on VPS |
| 2 | **Intake Service** | Normalize, tag (sentiment + category + tickers), and broadcast — drops noise in <5ms | Same process as news feed |
| 3 | **Redis Stream** | Persistent message queue with consumer groups (each consumer keeps idx of where it is at queue so they can all read contents of the single threaded non locking queue) |
| 4 | **Modal Agents** | One agent per market, subscribes to relevant tags, wakes on matching news, calls Groq, scales to zero | Modal (pay per use) |
| 5 | **Market Registry** | Tag-indexed market data in Redis linking on-chain markets to Groq decisions | Inside Redis |
| 6 | **Decision Queue** | Decouples classification from execution so trades queue if Solana is slow | Redis Stream |
| 7 | **Solana Executor** | Reads decisions, fires trades via proprietary API | Always-on process on VPS |
| 8 | **Position Monitor** | Polls open positions every 30s for resolution, edge compression, contradicting news, time decay | Same process as executor |

## How a Trade Happens

```
t=0ms     Reuters fires: "Fed raises rates 50bps surprise"
t=2ms     Intake dedup + keyword tag → [fed, macro] → written to news:raw stream
t=5ms     8 Modal agents subscribed to [fed] or [macro] wake up in parallel
t=10ms    Each agent prompts Groq with headline + its market + current price
t=380ms   Each agent gets back YES, NO, or skip for its market
t=385ms   Decisions written to decisions:raw stream, agents go back to sleep
t=390ms   Executor reads decisions, validates positions & market state
t=800ms   5 positions confirmed on-chain, tracked in Redis
t=48hrs   Markets resolve → claim winnings → record PnL
```

## Intake Pipeline

Every raw story passes through two gates:

1. **Keyword filter** — headline scanned for tradeable keywords → tagged `fed`, `crypto`, `macro`, `politics`, `sec`. No match → drop.
2. **Queue** — surviving stories written to `news:raw` Redis Stream with headline, body, source, tags, and timestamp.

## Modal Agents (Groq) — LIVE

Every market has its own agent deployed on Modal serverless. Each agent subscribes to the Redis tag channels matching its market's tags. When a story arrives on any subscribed channel, the agent wakes, classifies via Groq, and emits a Decision.

**Per-agent flow:**

1. Agent's listener subscribes to Redis tag channels (e.g. `fed`, `macro`) via pybind11 binding
2. Story arrives → thin Python wrapper calls Modal `MarketAgent.evaluate()`
3. Modal container prompts Groq (`llama-3.1-8b-instant`) with headline + market question + current probability
4. Groq returns JSON: `{"action": "YES"|"NO"|"SKIP", "confidence": 0.0-1.0, "reasoning": "..."}`
5. Non-SKIP decisions written to `decisions:raw` stream
6. Container stays warm for 5min, then scales to zero

**Measured latency (live on real news feed):**

| Metric | Cold start | Warm container |
|--------|-----------|----------------|
| Groq inference | 249ms | 249ms |
| Modal overhead | ~2700ms | ~50–80ms |
| **Total** | **~3000ms** | **~300–330ms** |

**Scaling:** 0 news → 0 containers → $0. One story matching 8 markets → 8 parallel evaluations. `@modal.concurrent(max_inputs=20)` means each container handles up to 20 Groq calls simultaneously (I/O-bound).

**Prompt evolution:**

| Version | Model | Groq latency | Issue |
|---------|-------|-------------|-------|
| v1 | llama-3.3-70b-versatile | 311ms | Model echoed prompt phrasing as action |
| v2 | llama-3.3-70b-versatile | ~300ms | Fixed with `_normalize_action()` parser |
| v3 | llama-3.1-8b-instant | 249ms | Compact prompt, faster model — **current** |

## Market Registry

Every Solana market is mirrored in Redis with tag indexes for fast lookup:

```
Key:   market:{address}
Value: { address, question, probability, tags, createdAt, expiresAt }

Tag indexes:
  tag:crypto   → SET of market addresses
  tag:fed      → SET of market addresses
  tag:macro    → SET of market addresses
  tag:politics → SET of market addresses
```

When a story tagged `crypto` arrives, `SMEMBERS tag:crypto` returns all relevant markets instantly.

## Solana Executor

Trade execution is handled via a proprietary API. The executor reads decisions from the queue and fires trades through this API — execution logic is abstracted away from the rest of the pipeline.

## Position Monitor

Continuous loop checking all open positions every 30 seconds:

| Check | Condition | Action |
|-------|-----------|--------|
| **Resolved** | Market settled on-chain | Claim winnings, remove position |
| **Edge compressed** | Current price vs entry < 3% | Take profit, exit |
| **Contradicting news** | New Groq signal is opposite | Exit early, take loss |
| **Time decay** | Near expiry, not in profit | Exit, redeploy capital |

## Repo Structure

```
trademaxxer/
├── server/
│   ├── main.py                      # Entry point — news stream + agent test harness
│   ├── config.py                    # Centralized env-based configuration
│   ├── requirements.txt
│   ├── core/
│   │   └── types.py                 # Base exceptions, reconnection state
│   ├── models/
│   │   └── news.py                  # RawNewsItem, TaggedNewsItem, enums
│   ├── dbnews_client/
│   │   ├── client.py                # WebSocket client with auto-reconnect
│   │   └── normalizer.py            # Raw DBNews JSON → RawNewsItem
│   ├── tagger/
│   │   └── tagger.py                # Sentiment, category, ticker extraction
│   ├── ws_server/
│   │   └── server.py                # WS server broadcasting tagged news to frontend
│   ├── agents/                      # Modal agent pipeline
│   │   ├── schemas.py               # MarketConfig, StoryPayload, Decision dataclasses
│   │   ├── prompts.py               # Versioned Groq prompt templates (v3)
│   │   ├── groq_client.py           # Async Groq wrapper with retry + action normalization
│   │   ├── agent_logic.py           # Pure evaluate(story, market, groq) → Decision
│   │   ├── modal_app.py             # Modal App — MarketAgent class deployed serverless
│   │   └── listener.py              # Per-market listener subscribing to tag channels
│   └── stream/                      # Stream abstraction layer
│       ├── interface.py             # Protocol: StreamProducer, TaggedStreamConsumer
│       └── stub.py                  # In-memory stub for local dev (Redis coming via pybind11)
├── client/
│   ├── client/                      # React frontend (Vite)
│   │   ├── src/
│   │   │   ├── App.jsx              # Live news feed UI
│   │   │   ├── App.css
│   │   │   └── main.jsx
│   │   ├── package.json
│   │   └── vite.config.js
│   └── src/
│       └── App.jsx
├── DEVLOG.md                        # Development log with benchmarks
└── README.md
```

## Infrastructure

```
Server 1 — VPS ($5/mo)
├── news websocket client
├── intake service
├── solana executor
└── position monitor

Server 2 — Modal (pay per use)
└── per-market groq agents

Server 3 — Upstash Redis (free tier)
├── news:raw stream
├── decisions:raw stream
├── market registry
└── position tracker
```

| Component | Host | Cost |
|-----------|------|------|
| News websocket | Railway / VPS | ~$5/mo |
| Intake service | Same VPS | — |
| Redis Streams | Upstash | Free tier |
| Modal classifier | Modal | ~$0.001/story |
| Solana executor | Same VPS | — |
| Position monitor | Same VPS | — |
| Frontend | Vercel | Free |
| **Total** | | **~$5–10/mo** |

## What We Build vs. What We Use

**Built from scratch:**

- News streamer / intake service (Python) — DBNews websocket, normalizer, tagger, WS broadcast
- Modal per-market agents (Python) — deployed and benchmarked
- Agent test harness — wired into news feed, measures end-to-end latency
- Stream abstraction layer — Protocol interfaces with in-memory stub
- Solana executor (Python) — TODO
- Frontend (React + Vite)

**Third-party:**

- DBNews — real-time news websocket feed
- Groq API — LLM inference (`llama-3.1-8b-instant`)
- VADER — financial sentiment analysis
- Redis / Upstash — streams & state (C++ binding via pybind11, in progress)
- Modal — serverless compute

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| News feed (DBNews WS) | **Live** | Streaming real-time, ~2 stories/sec |
| Intake / tagger | **Live** | Sentiment + category + tickers in <5ms |
| WS broadcast server | **Live** | Frontend connected |
| Modal agents (Groq) | **Deployed** | ~300ms warm, 20 concurrent per container |
| Stream abstraction | **Built** | Protocol + in-memory stub ready |
| Redis stream (C++) | In progress | pybind11 integration by another party |
| Solana executor | Not started | |
| Position monitor | Not started | |

See [DEVLOG.md](DEVLOG.md) for full development history and benchmarks.

## License

MIT
