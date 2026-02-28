# TradeMaxxer

Autonomous news-to-trade pipeline on Solana. Ingests real-time news, classifies it with Groq via Modal serverless, and executes trades on-chain — all in under one second, with no human in the loop.

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- Redis server (local or remote) — only needed for live mode
- [Modal](https://modal.com) account + API key — only needed for live mode
- [Groq](https://groq.com) API key — only needed for live mode

### 1. Server

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file (only needed for live mode):

```
GROQ_API_KEY=gsk_...
REDIS_URL=redis://localhost:6379/0
DBNEWS_WS_URL=wss://...
```

### 2. Modal setup (only needed for live mode)

```bash
pip install modal
modal setup          # opens browser to authenticate your Modal account
```

Then store your Groq API key as a Modal secret — the deployed agent containers read it from there, not from `.env`:

```bash
modal secret create groq-api-key GROQ_API_KEY=gsk_...
```

This creates a secret called `groq-api-key` in your Modal workspace that the `MarketAgent` class references via `modal.Secret.from_name("groq-api-key")`.

### 3. Frontend

```bash
cd client/client
npm install
```

### 4. Run

**Mock mode** — no external services needed, generates fake news + fake agent decisions:

```bash
# Terminal 1: backend
cd server && python3 main.py --mock

# Terminal 2: frontend
cd client/client && npm run dev
```

Open `http://localhost:5173` — the Bloomberg Terminal dashboard will start populating with mock data immediately.

**Live mode** — requires Redis, Modal deployed, DBNews credentials:

```bash
# Terminal 0: Redis
redis-server

# Terminal 1: deploy Modal agents (one-time, re-run after code changes)
cd server && modal deploy agents/modal_app.py

# Terminal 2: backend
cd server && python3 main.py

# Terminal 3: frontend
cd client/client && npm run dev
```

To verify Modal is working before starting the full pipeline:

```bash
# Quick smoke test — should print a Decision dict
cd server && python3 -c "
import modal, asyncio
AgentCls = modal.Cls.from_name('trademaxxer-agents', 'MarketAgent')
agent = AgentCls()
result = asyncio.run(agent.evaluate.remote.aio(
    {'id': 'test', 'headline': 'Test headline', 'body': '', 'tags': ['test'], 'source': 'test', 'timestamp': '2026-01-01T00:00:00+00:00'},
    {'address': 'TestAddr', 'question': 'Test?', 'current_probability': 0.5, 'tags': ['test'], 'expires_at': None}
))
print(result)
"
```

## Architecture

```
NEWS FEED ──→ INTAKE / TAGGER ──→ REDIS PUB/SUB ──→ MODAL AGENTS (Groq) ──→ DASHBOARD
                                                                             │
                                                                     (not yet built)
                                                                             ↓
                                                                   SOLANA EXECUTOR ──→ POSITION MONITOR
```

### Components

| # | Component | What it does | Runtime |
|---|-----------|-------------|---------|
| 1 | **News Feed** | WebSocket connection to DBNews provider (~2 stories/sec, spikes during major events). Mock mode generates 100 realistic headlines. | Always-on Python process on VPS |
| 2 | **Intake Service** | Normalize, tag (sentiment + category + tickers), and broadcast — drops noise in <5ms | Same process as news feed |
| 3 | **Redis Pub/Sub** | Tag-based fan-out channels (`news:all`, `news:category:macro`, etc.). Each listener subscribes to its market's tags. | Local or Upstash Redis |
| 4 | **Modal Agents** | One agent per market, subscribes to relevant tags, wakes on matching news, calls Groq, scales to zero. Mock mode returns random decisions inline. | Modal (pay per use) |
| 5 | **Dashboard** | Bloomberg Terminal-style UI with 13 live panels: news wire, decision feed, position book, charts, ticker tape, latency stats | React + Vite (local or Vercel) |
| 6 | **Market Registry** | Tag-indexed market data linking on-chain markets to Groq decisions | Planned — currently hardcoded `MarketConfig` |
| 7 | **Solana Executor** | Reads decisions, fires trades via proprietary API | Not started |
| 8 | **Position Monitor** | Polls open positions every 30s for resolution, edge compression, contradicting news, time decay | Not started |

## How a Trade Happens

```
t=0ms     Reuters fires: "Fed raises rates 50bps surprise"
t=2ms     Intake dedup + keyword tag → [fed, macro] → published to news:category:macro channel
t=5ms     4 agents subscribed to [fed] or [macro] wake up in parallel
t=10ms    Each agent prompts Groq with headline + its market + current price
t=300ms   Each agent gets back YES, NO, or SKIP for its market
t=305ms   Decisions broadcast to dashboard via WebSocket
t=310ms   (future) Executor reads decisions, validates positions & market state
t=800ms   (future) Positions confirmed on-chain, tracked in Redis
t=48hrs   (future) Markets resolve → claim winnings → record PnL
```

## Intake Pipeline

Every raw story passes through two gates:

1. **Tagger** — headline scanned for sentiment (VADER), categories (`geopolitics`, `macro`, `crypto`, etc.), and tickers. Categories determine which Redis channels the story publishes to.
2. **Fan-out** — tagged story broadcast to WebSocket (dashboard) and published to Redis Pub/Sub channels (`news:all` + per-category channels).

## Modal Agents (Groq) — LIVE

Every market has its own agent deployed on Modal serverless. Each agent's listener subscribes to the Redis Pub/Sub channels matching its market's tags. When a story arrives on any subscribed channel, the listener calls Modal, which runs Groq classification and emits a Decision.

**Per-agent flow:**

1. `AgentListener` subscribes to Redis channels (e.g. `news:all`, `news:category:macro`) via `FeedSubscriber`
2. Story arrives → deduplication via `seen` set → deserialize to `StoryPayload`
3. Calls Modal `MarketAgent.evaluate()` remotely (or `mock_evaluate()` in mock mode)
4. Modal container prompts Groq (`llama-3.1-8b-instant`) with headline + market question + current probability
5. Groq returns JSON: `{"action": "YES"|"NO"|"SKIP", "confidence": 0.0-1.0, "reasoning": "..."}`
6. Decision broadcast to dashboard via WebSocket `on_decision` callback
7. Container stays warm for 5min (`scaledown_window=300`), then scales to zero

**Measured latency (live on real news feed):**

| Metric | Cold start | Warm container |
|--------|-----------|----------------|
| Groq inference | 249ms | 249ms |
| Modal overhead | ~2700ms | ~50–80ms |
| **Total** | **~3000ms** | **~300–330ms** |

Modal warm-up fires a dummy evaluation at startup to avoid cold starts on the first real trade.

**Scaling:** 0 news → 0 containers → $0. One story matching 4 markets → 4 parallel evaluations. `@modal.concurrent(max_inputs=20)` means each container handles up to 20 Groq calls simultaneously (I/O-bound). `buffer_containers=1` keeps one pre-warmed.

**Prompt evolution:**

| Version | Model | Groq latency | Issue |
|---------|-------|-------------|-------|
| v1 | llama-3.3-70b-versatile | 311ms | Model echoed prompt phrasing as action |
| v2 | llama-3.3-70b-versatile | ~300ms | Fixed with `_normalize_action()` parser |
| v3 | llama-3.1-8b-instant | 249ms | Compact prompt, faster model — **current** |

## Mock Mode

`python3 main.py --mock` runs the full pipeline with zero external dependencies:

- **100 realistic headlines** covering geopolitics, macro, commodities, crypto, politics — randomly fired at 1–4s intervals
- **Mock agent evaluator** returns random YES/NO/SKIP decisions with simulated 150–400ms latency, realistic confidence values, and canned reasoning
- Each headline generates 4 decisions (one per test market), all broadcast to the dashboard
- No Redis, no Modal, no DBNews, no API keys needed

Useful for UI development, demo purposes, and testing the full event flow end-to-end.

## Dashboard

Bloomberg Terminal-style real-time UI built with React, Tailwind CSS, and Recharts.

**Panels:**

| Panel | What it shows |
|-------|--------------|
| **Terminal Header** | Connection status (WS/Redis/Modal/Groq), event + decision counts, throughput rates (ev/s, dec/s), hit rate, YES%, uptime, UTC clock |
| **Ticker Tape** | Auto-scrolling ribbon of latest decisions — action, address, confidence, latency |
| **News Wire** | Dense feed of incoming headlines with urgency badges, sentiment indicators, category tags, age, velocity (items/s) |
| **Markets** | Table with probability, signal strength bars, YES/NO/SKIP counts, avg confidence, latency sparklines |
| **Position Book** | Per-market YES/NO pressure bars, avg confidence, confidence sparklines, simulated P&L |
| **Tag Heatmap** | Category tiles with intensity-scaled backgrounds showing frequency distribution |
| **Decision Feed** | Full decision details — action, confidence bar, latency, prompt version, market question, reasoning, source headline |
| **Latency Chart** | Real-time line chart of per-decision latency |
| **Throughput Chart** | Area chart of events/sec and decisions/sec over time |
| **Confidence Histogram** | Distribution of confidence values across 5 buckets with mean |
| **Decision Distribution** | Bar chart of YES/NO/SKIP totals |
| **Latency Stats** | MIN/P50/AVG/P95/P99/MAX with visual bars, standard deviation, range |
| **System Bar** | Aggregate metrics — status, rates, action breakdowns, latency stats, version |

All panels update in real-time via WebSocket. CRT scanline overlay for aesthetics. Monospace font (JetBrains Mono). Zero border-radius.

## Repo Structure

```
trademaxxer/
├── server/
│   ├── main.py                          # Entry point — orchestrator, --mock flag
│   ├── mock_feed.py                     # Mock headlines + mock agent evaluator
│   ├── requirements.txt
│   ├── .env                             # GROQ_API_KEY, REDIS_URL (not committed)
│   ├── news_streamer/
│   │   ├── config.py                    # Env-based configuration
│   │   ├── core/types.py                # Base exceptions, reconnection state
│   │   ├── models/news.py               # RawNewsItem, TaggedNewsItem, enums
│   │   ├── dbnews_client/client.py      # DBNews WebSocket client with auto-reconnect
│   │   ├── dbnews_client/normalizer.py  # Raw JSON → RawNewsItem
│   │   ├── tagger/tagger.py             # Sentiment, category, ticker extraction
│   │   ├── ws_server/server.py          # WS server — broadcasts news + decisions
│   │   ├── pubsub/publisher.py          # NewsPublisher — Redis pub/sub fan-out
│   │   ├── pubsub/channels.py           # Channel name constants
│   │   ├── pubsub/serializer.py         # TaggedNewsItem → wire dict
│   │   └── lib/sentiment_analyzer.py    # VADER wrapper
│   ├── agents/
│   │   ├── schemas.py                   # MarketConfig, StoryPayload, Decision
│   │   ├── prompts.py                   # Versioned Groq prompt templates (v3)
│   │   ├── groq_client.py              # Async Groq wrapper + action normalization
│   │   ├── agent_logic.py              # evaluate(story, market, groq) → Decision
│   │   ├── modal_app.py                # Modal App definition — deployed serverless
│   │   └── listener.py                 # Per-market Redis subscriber → Modal caller
│   ├── pub_sub_feed/                   # Redis pub/sub library
│   │   ├── publisher.py                # FeedPublisher
│   │   ├── subscriber.py              # FeedSubscriber (pull-based)
│   │   └── serializer.py              # Wire serialization
│   └── stream/                         # Legacy stream abstraction
│       ├── interface.py                # Protocol: StreamProducer, TaggedStreamConsumer
│       └── stub.py                     # In-memory stub
├── client/client/                      # React frontend (Vite + Tailwind)
│   ├── src/
│   │   ├── App.jsx                     # 3-column layout orchestrator
│   │   ├── index.css                   # Bloomberg Terminal theme + animations
│   │   ├── main.jsx                    # React entry point
│   │   ├── hooks/useWebSocket.js       # WS connection, state management, metrics
│   │   └── components/
│   │       ├── TerminalHeader.jsx      # Top bar — status, metrics, clock
│   │       ├── TickerTape.jsx          # Scrolling decision ribbon
│   │       ├── NewsTape.jsx            # News feed with velocity
│   │       ├── DecisionFeed.jsx        # Decision stream with full details
│   │       ├── MarketGrid.jsx          # Market table with signal strength
│   │       ├── PositionBook.jsx        # YES/NO pressure + simulated P&L
│   │       ├── TagHeatmap.jsx          # Category frequency heatmap
│   │       ├── LatencyChart.jsx        # Latency line chart
│   │       ├── ThroughputChart.jsx     # Events/sec + decisions/sec area chart
│   │       ├── ConfidenceHistogram.jsx # Confidence distribution
│   │       ├── DecisionChart.jsx       # YES/NO/SKIP bar chart
│   │       ├── LatencyStats.jsx        # Percentile breakdown
│   │       └── SystemBar.jsx           # Footer status bar
│   ├── package.json
│   └── vite.config.js
├── DEVLOG.md                           # Development log with benchmarks
└── README.md
```

## Infrastructure

```
Server 1 — VPS ($5/mo)
├── news websocket client (DBNews)
├── intake service (tagger + fan-out)
├── Redis pub/sub publisher
├── agent listeners (1 per market)
├── WebSocket server (dashboard)
├── (future) solana executor
└── (future) position monitor

Server 2 — Modal (pay per use)
└── per-market Groq agents (MarketAgent class)

Server 3 — Redis (local or Upstash free tier)
├── news:all channel
├── news:category:* channels
└── (future) market registry, position tracker

Server 4 — Vercel (free)
└── frontend dashboard
```

| Component | Host | Cost |
|-----------|------|------|
| News + intake + listeners | Railway / VPS | ~$5/mo |
| Redis Pub/Sub | Local / Upstash | Free tier |
| Modal agents | Modal | ~$0.001/story |
| Frontend | Vercel | Free |
| **Total** | | **~$5–10/mo** |

## What We Build vs. What We Use

**Built from scratch:**

- News streamer / intake service — DBNews websocket, normalizer, tagger, WS broadcast, Redis pub/sub publisher
- Modal per-market agents — deployed, benchmarked, warm-up system
- Per-market listeners — tag-based Redis subscription, deduplication, Modal invocation
- Mock system — 100 headlines, random agent evaluator, full offline pipeline
- Bloomberg Terminal dashboard — 13 panels, real-time WebSocket, charts, animations
- Stream abstraction layer — Protocol interfaces (legacy, superseded by `pub_sub_feed`)

**Third-party:**

- DBNews — real-time news websocket feed
- Groq API — LLM inference (`llama-3.1-8b-instant`)
- VADER — financial sentiment analysis
- Redis — pub/sub message fan-out
- Modal — serverless compute
- Recharts — chart rendering
- Tailwind CSS — styling

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| News feed (DBNews WS) | **Live** | Streaming real-time, ~2 stories/sec |
| Mock news feed | **Live** | 100 headlines, `--mock` flag |
| Intake / tagger | **Live** | Sentiment + category + tickers in <5ms |
| WS broadcast server | **Live** | News + decisions to dashboard |
| Redis Pub/Sub | **Live** | Python `pub_sub_feed` library, tag-based channels |
| Modal agents (Groq) | **Deployed** | ~300ms warm, 20 concurrent per container |
| Mock agents | **Live** | Random decisions, 150–400ms simulated latency |
| Agent listeners | **Live** | 1 per market, deduplication, `news:all` fallback |
| Dashboard | **Live** | Bloomberg Terminal, 13 panels, real-time |
| Market registry | Planned | Currently hardcoded `MarketConfig` objects |
| Decision queue | Planned | Decisions go direct to dashboard, no queue yet |
| Solana executor | Not started | |
| Position monitor | Not started | |

See [DEVLOG.md](DEVLOG.md) for full development history and benchmarks.

## License

MIT
