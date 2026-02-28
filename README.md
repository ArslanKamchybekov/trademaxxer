# TradeMaxxer

Autonomous news-to-trade pipeline on Solana. Ingests real-time news, classifies it with a pretrained NLI model on Modal serverless, and executes trades on-chain — all with no human in the loop.

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- Redis server (local or remote) — only needed for live mode
- [Modal](https://modal.com) account + API key — only needed for live mode

### 1. Server

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your DBNews credentials (only needed for live mode):

```
DBNEWS_USERNAME=...
DBNEWS_PASSWORD=...
DBNEWS_WS_URL=wss://dbws.io
REDIS_URL=redis://localhost:6379/0
```

### 2. Modal setup (only needed for live mode)

```bash
pip install modal
modal setup          # opens browser to authenticate your Modal account
```

Deploy the NLI agent to Modal:

```bash
cd server
modal deploy agents/modal_app_fast.py
```

This builds a container image with the pretrained `cross-encoder/nli-deberta-v3-xsmall` model baked in. No API keys or secrets needed — the model runs locally inside the container.

### 3. Frontend

```bash
cd client/client
npm install
```

### 4. Run

**One command (recommended):**

```bash
./start.sh --mock    # mock mode: no external services needed
./start.sh           # live mode: Redis + DBNews + Modal NLI agents
```

This starts Redis (live mode only), the Python server, and the Vite dev server. Ctrl-C stops everything.

Open `http://localhost:5173` — the Bloomberg Terminal dashboard will start populating immediately.

**Manual (if you prefer separate terminals):**

```bash
# Mock mode — no external services
cd server && python3 main.py --mock          # Terminal 1
cd client/client && npm run dev              # Terminal 2

# Live mode — requires Redis + Modal deployed
redis-server                                 # Terminal 1
cd server && python3 main.py                 # Terminal 2
cd client/client && npm run dev              # Terminal 3
```

To verify Modal is working before starting the full pipeline:

```bash
cd server && python3 -c "
import modal, asyncio
Cls = modal.Cls.from_name('trademaxxer-agents-fast', 'FastMarketAgent')
agent = Cls()
result = asyncio.run(agent.evaluate_batch.remote.aio([
    {'headline': 'Fed raises rates 50bps', 'question': 'Will the Fed cut rates?',
     'probability': 0.5, 'market_address': 'test', 'story_id': 'test'}
]))
print(result)
"
```

## Architecture

```
NEWS FEED ──→ INTAKE / TAGGER ──→ DIRECT DISPATCH ──→ MODAL AGENTS (ONNX NLI) ──→ DASHBOARD
                                  (tag-filter + batch)     │
                                                    (not yet built)
                                                           ↓
                                                 SOLANA EXECUTOR ──→ POSITION MONITOR
```

The hot path is **zero-Redis**: news arrives, gets tagged in-process, filtered against armed markets by tag overlap, chunked into batches of 50, and fired as parallel Modal RPCs. Redis remains in the codebase for future cross-process deployment but is not on the critical latency path.

### Components

| # | Component | What it does | Runtime |
|---|-----------|-------------|---------|
| 1 | **News Feed** | WebSocket connection to DBNews provider (~2 stories/sec, spikes during major events). Mock mode generates 100 realistic headlines. | Always-on Python process on VPS |
| 2 | **Intake Service** | Normalize, tag (sentiment + category + tickers), and broadcast — drops noise in <5ms | Same process as news feed |
| 3 | **Direct Dispatch** | Tag-filter enabled markets, chunk into batches of 50, fire parallel `asyncio.gather()` RPCs to Modal. Replaces Redis in the hot path. | Same process |
| 4 | **Modal Agents (ONNX)** | Batched NLI inference via ONNX Runtime. One RPC evaluates up to 50 markets. Scales horizontally — 5k markets = 100 parallel RPCs, same wall-clock time. | Modal (pay per use) |
| 5 | **Dashboard** | Bloomberg Terminal-style UI with 13 live panels: news wire, decision feed, position book, charts, ticker tape, latency stats. Includes per-market agent toggle. | React + Vite (local or Vercel) |
| 6 | **Market Registry** | Tag-indexed market data linking on-chain markets to agent decisions | Planned — currently hardcoded `MarketConfig` |
| 7 | **Solana Executor** | Reads decisions, fires trades via proprietary API | Not started |
| 8 | **Position Monitor** | Polls open positions every 30s for resolution, edge compression, contradicting news, time decay | Not started |

## How a Trade Happens

```
t=0ms     Reuters fires: "Fed raises rates 50bps surprise"
t=2ms     Intake dedup + keyword tag → [fed, macro]
t=3ms     Tag-filter: 4/12 armed markets match [fed] or [macro]
t=4ms     Batch: 4 markets chunked into 1 batch (< 50 threshold)
t=5ms     Single Modal RPC fired (ONNX NLI, evaluate_batch)
t=40ms    ONNX inference completes (~35ms for batch of 4)
t=85ms*   RPC returns — 4 decisions with action + confidence
t=86ms    Decisions broadcast to dashboard (fire-and-forget)
t=90ms    (future) Executor reads decisions, validates positions
t=800ms   (future) Positions confirmed on-chain
t=48hrs   (future) Markets resolve → claim winnings → record PnL

* 85ms assumes co-located VPS. From local Mac: ~140-200ms.
```

## Intake Pipeline

Every raw story passes through two gates:

1. **Tagger** — headline scanned for sentiment (VADER), categories (`geopolitics`, `macro`, `crypto`, etc.), and tickers. Categories determine which Redis channels the story publishes to.
2. **Fan-out** — tagged story broadcast to WebSocket (dashboard) and published to Redis Pub/Sub channels (`news:all` + per-category channels).

## Modal Agents (ONNX NLI) — LIVE

News-to-decision classification runs on Modal as an ONNX Runtime model. No LLM, no API keys, no rate limits. The entire inference stack fits in a ~300MB container image.

**Model:** `cross-encoder/nli-deberta-v3-xsmall` (22M params, ONNX Runtime, CPU inference)

Classification is framed as Natural Language Inference:
- **Premise:** news headline
- **Hypothesis:** market question (e.g. "Will oil exceed $120/barrel?")
- **Output:** entailment → YES, contradiction → NO, neutral → SKIP

Confidence is scaled by market probability — signals already priced in get discounted.

**Hot path (direct dispatch):**

1. News arrives → tagger extracts categories in ~5ms
2. `_nli_eval_and_broadcast()` filters: only armed markets whose tags overlap with story tags
3. Matching markets chunked into batches of 50
4. Parallel `asyncio.gather()` fires one Modal RPC per chunk
5. Modal container runs ONNX inference: tokenize → `session.run()` → softmax → postprocess
6. Returns `[{"action": "YES"|"NO"|"SKIP", "confidence": 0.0-1.0, "reasoning": "..."}, ...]`
7. Each decision broadcast to dashboard via fire-and-forget `asyncio.create_task()`
8. Container stays warm for 5min (`scaledown_window=300`), then scales to zero

**Why ONNX NLI over Groq LLM:**

| | Groq (llama-3.1-8b-instant) | ONNX NLI (DeBERTa-v3-xsmall) |
|---|---|---|
| Inference | ~250ms | **~35ms** (batch of 12) |
| Rate limits | 6000 TPM free tier | **None** |
| API dependency | External (Groq) | **None** (model baked in image) |
| Cost per call | Token-based | **CPU time only** |
| Batch support | No | **Yes** (single forward pass) |
| Image size | ~600MB (groq SDK) | **~300MB** (onnxruntime) |
| Cold start | ~3s | **~1.5s** |

**Scaling:** 0 news → 0 containers → $0. One story matching 50 markets → 1 RPC. 5,000 matching markets → 100 parallel RPCs, same wall-clock time. `buffer_containers=1` keeps one pre-warmed.

**Model evolution:**

| Version | Model | Runtime | Inference | Total (warm) | Issue |
|---------|-------|---------|-----------|-------------|-------|
| v1 | llama-3.3-70b-versatile | Groq API | 311ms | ~658ms | Verbose output, parsing failures |
| v2 | llama-3.3-70b-versatile | Groq API | ~300ms | ~600ms | Fixed parser |
| v3 | llama-3.1-8b-instant | Groq API | 249ms | ~300ms | Rate limited at 6000 TPM |
| nli-v1 | DeBERTa-v3-xsmall | PyTorch | ~40ms | ~200ms | Large image (1.5GB) |
| **nli-v2** | DeBERTa-v3-xsmall | **ONNX** | **~35ms** | **~143ms** | **Current** — 300MB image |

## Latency Breakdown

Measured from local Mac (residential internet → Modal cloud):

```
Stage                    Time        Cumulative
─────────────────────────────────────────────────
Tagger (VADER + regex)   ~5ms        5ms
Tag-filter + chunk       <1ms        6ms
Modal RPC overhead       ~100ms*     106ms
ONNX tokenize + infer    ~35ms       141ms
Postprocess + return     ~2ms        143ms
WS broadcast             async       (non-blocking)
─────────────────────────────────────────────────
Total (local Mac)                    ~143-200ms
Total (co-located VPS)               ~65-85ms  (projected)
Total (Modal-hosted)                 ~40ms     (planned)

* RPC overhead = network round-trip + Modal scheduling.
  From a co-located VPS this drops to ~30-50ms.
```

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
│   │   ├── nli_postprocess.py           # NLI logits → YES/NO/SKIP + confidence scaling
│   │   ├── modal_app_fast.py            # Modal App (NLI) — current deployed agent
│   │   ├── modal_app.py                 # Modal App (Groq) — legacy, superseded
│   │   ├── prompts.py                   # Versioned Groq prompt templates (legacy)
│   │   ├── groq_client.py              # Async Groq wrapper (legacy)
│   │   ├── agent_logic.py              # evaluate(story, market, groq) → Decision (legacy)
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
├── start.sh                            # One-command launcher (Redis + server + frontend)
├── DEVLOG.md                           # Development log with benchmarks
├── ARCHITECTURE.md                     # Mermaid diagrams — all system flows
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
└── per-market NLI agents (FastMarketAgent class)

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
- Modal NLI agents — pretrained DeBERTa model, batched inference, warm-up system
- NLI postprocessor — logit mapping, probability-aware confidence scaling
- Per-market listeners — tag-based Redis subscription, deduplication, Modal invocation
- Mock system — 100 headlines, random agent evaluator, full offline pipeline
- Bloomberg Terminal dashboard — 13 panels, real-time WebSocket, charts, animations
- Single-command launcher (`start.sh`)

**Third-party:**

- DBNews — real-time news websocket feed
- HuggingFace `cross-encoder/nli-deberta-v3-xsmall` — pretrained NLI model
- VADER — financial sentiment analysis
- Redis — pub/sub message fan-out
- Modal — serverless compute
- Recharts — chart rendering
- Tailwind CSS — styling

## Dynamic Market Management

Markets default to **OFF**. The user arms specific markets from the dashboard — only armed markets consume compute.

- **Toggle:** Click the agent toggle in the Markets panel to arm/disarm a market
- **Server-authoritative:** Backend owns the `enabled_markets` set. UI sends requests, server validates and broadcasts.
- **Tag-filter:** Armed markets only get evaluated if story tags overlap with market tags.
- **Visual feedback:** Unarmed markets are dimmed (30% opacity), header shows "X/Y armed".

This is critical for scaling to 5,000+ markets from a real registry. You arm markets you have edge on, not all of them.

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| News feed (DBNews WS) | **Live** | Streaming real-time, ~2 stories/sec |
| Mock news feed | **Live** | 100 headlines, `--mock` flag |
| Intake / tagger | **Live** | Sentiment + category + tickers in <5ms |
| WS broadcast server | **Live** | News + decisions + market state to dashboard |
| Direct dispatch | **Live** | Tag-filter → chunk → parallel Modal RPCs |
| Modal agents (ONNX) | **Deployed** | DeBERTa-v3-xsmall ONNX, ~35ms inference, no rate limits |
| Dynamic market toggle | **Live** | UI-driven arm/disarm, server-authoritative |
| Mock agents | **Live** | Random decisions, 150–400ms simulated latency |
| Dashboard | **Live** | Bloomberg Terminal, 13 panels, real-time, market toggles |
| Redis Pub/Sub | Available | Not on hot path — kept for future multi-process mode |
| Market registry | Planned | Currently hardcoded `MarketConfig` objects |
| Decision queue | Planned | Decisions go direct to dashboard, no queue yet |
| Solana executor | Not started | |
| Position monitor | Not started | |

See [DEVLOG.md](DEVLOG.md) for full development history, benchmarks, and architecture decisions.
See [ARCHITECTURE.md](ARCHITECTURE.md) for mermaid diagrams of all system flows.

## License

MIT
