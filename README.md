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

## Modal Agents (Groq)

Every market has its own agent — a persistent serverless function on Modal that subscribes to the tags relevant to that market. When a story hits `news:raw` with a matching tag, the agent wakes up.

**Per-agent flow:**

1. Agent receives story from `news:raw` stream (filtered to its subscribed tags)
2. Prompt Groq (`llama3-70b-8192`) with just the headline, the agent's market, and current price
3. Groq returns a single decision: `YES`, `NO`, or `skip`
4. Push decision to `decisions:raw` stream
5. Agent goes back to sleep

Each agent is scoped to one market and only sees news that matches its tags. A story tagged `[fed, macro]` wakes up every agent subscribed to `fed` or `macro` — they all evaluate in parallel, independently.

**Scaling:** 0 news → 0 active agents → $0. One story matching 8 markets → 8 agents wake in parallel. Latency ~300–400ms per agent.

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
│   └── news_streamer/               # News intake + tagging service (Python)
│       ├── main.py                  # Entry point — connects to DBNews, tags, broadcasts
│       ├── config.py                # Centralized env-based configuration
│       ├── requirements.txt
│       ├── core/
│       │   └── types.py             # Base exceptions, reconnection state
│       ├── models/
│       │   └── news.py              # RawNewsItem, TaggedNewsItem, enums (Sentiment, Category, Urgency)
│       ├── dbnews_client/
│       │   ├── client.py            # WebSocket client with auto-reconnect
│       │   └── normalizer.py        # Raw DBNews JSON → RawNewsItem
│       ├── tagger/
│       │   └── tagger.py            # Sentiment analysis, category classification, ticker extraction
│       └── ws_server/
│           └── server.py            # WebSocket server broadcasting tagged news to frontend clients
├── client/
│   ├── client/                      # React frontend (Vite)
│   │   ├── src/
│   │   │   ├── App.jsx              # Live news feed UI — sentiment, urgency, tickers
│   │   │   ├── App.css
│   │   │   └── main.jsx
│   │   ├── package.json
│   │   └── vite.config.js
│   └── src/
│       └── App.jsx                  # Alternate client entry
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
- Modal per-market agents (Python)
- Solana executor (Python)
- Frontend (React + Vite)

**Third-party:**

- DBNews — real-time news websocket feed
- Groq API — LLM inference
- VADER — financial sentiment analysis
- Redis / Upstash — streams & state
- Modal — serverless compute

## License

MIT
