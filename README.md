# TradeMaxxer

**Autonomous news-to-trade execution engine for Solana prediction markets.**

Real-time news ingestion, NLI-based signal classification via in-process ONNX inference, and on-chain execution — end-to-end in **16–69ms**. No human in the loop.

---

<p align="center">

**16ms** news-to-decision &nbsp;·&nbsp; **22M param** ONNX NLI model &nbsp;·&nbsp; **5,000+ markets** parallel eval &nbsp;·&nbsp; **$0/inference** local mode &nbsp;·&nbsp; **13-panel** Bloomberg Terminal UI

</p>

---

## The Problem

Prediction markets on Solana reprice based on real-world news. The window between a headline hitting the wire and the market adjusting is **seconds**. Manual traders can't react fast enough. LLM-based systems (GPT, Groq) are too slow (250ms+ per inference) and rate-limited. Most bots don't even attempt semantic understanding — they pattern-match keywords.

## Our Approach

TradeMaxxer frames news classification as a **Natural Language Inference** problem. Instead of asking an LLM "should I buy?", we treat each headline as a *premise* and each market question as a *hypothesis*, then measure entailment:

| Premise (headline) | Hypothesis (market) | NLI Output | Action |
|---|---|---|---|
| "Fed raises rates 50bps in surprise move" | "Will the Fed cut rates before July?" | **Contradiction** | **NO** — sell |
| "Iran strikes Israeli military base" | "Will the US engage in conflict with Iran?" | **Entailment** | **YES** — buy |
| "Apple announces new MacBook colors" | "Will oil exceed $120/barrel?" | **Neutral** | **SKIP** — ignore |

This runs on a 22M parameter DeBERTa model via ONNX Runtime — no GPU needed, no API calls, no rate limits. The entire inference stack fits in a 300MB container.

## Architecture

```
REAL-TIME NEWS ──→ INTAKE ──→ DISPATCH ──→ MODAL (ONNX NLI) ──→ EXECUTOR ──→ SOLANA
     │              5ms         1ms          35ms inference        │
     │                                       85ms total            │
     └───────────────────── DASHBOARD ←────────────────────────────┘
                         (13-panel Bloomberg Terminal)
```

| Component | What it does | Latency |
|---|---|---|
| **News Feed** | WebSocket connection to DBNews (~2 stories/sec, spikes to 10+ during events) | Real-time stream |
| **Intake / Tagger** | VADER sentiment, category extraction (geopolitics, macro, crypto, etc.), ticker detection | ~5ms |
| **Direct Dispatch** | Tag-filter armed markets, chunk into batches of 50, fire parallel RPCs via `asyncio.gather()` | <1ms |
| **Modal Agents** | ONNX Runtime NLI inference. One RPC evaluates 50 markets. 5k markets = 100 parallel RPCs, same wall-clock. | ~35ms inference |
| **Executor** | Validates decision against position state, market conditions, and risk limits. Fires trades via Solana RPC. | ~10ms |
| **Position Monitor** | Polls open positions for resolution, edge compression, contradicting signals, time decay. Auto-exits. | 30s interval |
| **Market Registry** | Tag-indexed market data from on-chain state. Links Solana market addresses to agent configurations. | Cached |
| **Dashboard** | 13-panel Bloomberg Terminal UI. Real-time WebSocket. Per-market agent toggles. CRT aesthetic. | <16ms render |

## How a Trade Happens

```
t=0ms     Reuters wire: "Fed raises rates 50bps in surprise move"
t=2ms     Intake: dedup → VADER sentiment (-0.73) → categories [fed, macro]
t=3ms     Dispatch: 4/312 armed markets match [fed] or [macro] tags
t=4ms     Batch: 4 markets → 1 chunk → local ONNX inference
t=20ms    ONNX tokenize + session.run() + softmax + postprocess completes
t=22ms    Decisions: [{action: "NO", confidence: 0.81, market: "FedRateCut..."}, ...]
t=23ms    Dashboard updated (fire-and-forget, non-blocking)
t=25ms    Executor validates: position check → risk limits → order construction
t=30ms    Solana RPC: sell order submitted
t=800ms   Position confirmed on-chain
t=48hrs   Market resolves → winnings claimed → PnL recorded
```

**16–69ms from headline to trade signal.** The entire inference pipeline runs in-process — zero network overhead.

## Performance

### Latency Breakdown (local ONNX, `--local` flag)

```
Stage                        Time        Cumulative
──────────────────────────────────────────────────────
Tagger (VADER + regex)       ~5ms        5ms
Tag-filter + chunk           <1ms        6ms
ONNX tokenize + inference    ~10-35ms    16-41ms
Postprocess + return         ~1ms        17-42ms
WS broadcast                 async       (non-blocking)
──────────────────────────────────────────────────────
Best case                                ~16ms
Worst case                               ~69ms
Typical                                  ~20-40ms
```

### Optimization Journey

We iterated through 6 model versions to reach current performance:

| Version | Model | Runtime | Inference | E2E (warm) | Why we moved on |
|---------|-------|---------|-----------|-----------|-----------------|
| v1 | Llama 3.3 70B | Groq API | 311ms | 658ms | Verbose output, unparseable responses |
| v2 | Llama 3.3 70B | Groq API | ~300ms | 600ms | Still too slow for trading |
| v3 | Llama 3.1 8B | Groq API | 249ms | 300ms | Rate limited at 6,000 TPM — dead at scale |
| v4 | DeBERTa-v3-xsmall | PyTorch on Modal | ~40ms | 200ms | 1.5GB image, slow cold starts |
| v5 | DeBERTa-v3-xsmall | ONNX on Modal | ~35ms | ~143ms | Modal RPC overhead 100-260ms |
| **v6** | **DeBERTa-v3-xsmall** | **ONNX local** | **~16ms** | **~16-69ms** | **Current** |

**4.3–18.8x faster than Groq. Zero rate limits. Zero API keys. Zero network.**

### What We Optimized

| Optimization | Latency saved | How |
|---|---|---|
| Groq LLM → ONNX NLI | **-215ms** | Replaced 8B LLM API call with 22M param ONNX model |
| Redis hot path elimination | **-8ms** | In-process dispatch replaces publish→subscribe roundtrip |
| PyTorch → ONNX Runtime | **-10ms** | Dropped autograd, GPU kernels, 1.2GB of torch |
| Modal RPC → local inference | **-100–260ms** | In-process ONNX call, zero network overhead |
| Blocking WS → fire-and-forget | **-5ms** | `asyncio.create_task()` for all non-critical I/O |
| Per-market RPC → batched | **cost + variance** | 1 call per 50 markets vs N concurrent RPCs — reduces scheduling contention and container sprawl |
| Image size: 1.5GB → 300MB | **-1.5s cold** | Faster container provisioning (Modal mode) |

### Scaling Characteristics

| Markets | Chunks (batch=50) | Parallel calls | Wall-clock time |
|---|---|---|---|
| 1 | 1 | 1 | ~16-40ms |
| 50 | 1 | 1 | ~30-69ms |
| 500 | 10 | 10 (threaded) | ~30-69ms |
| 5,000 | 100 | 100 (Modal) | ~85ms (cloud) |

Local mode: wall-clock scales slightly with batch size but stays sub-70ms for reasonable market counts. For 5k+ markets, Modal cloud mode with parallel RPCs is still available via `--local` omission.

## Confidence Scaling

Raw NLI confidence is adjusted by current market probability to avoid trading signals that are already priced in:

| Action | Formula | Intuition |
|---|---|---|
| YES | `confidence × (1 - market_prob)` | YES at 95% prob → already priced in → discount |
| NO | `confidence × market_prob` | NO at 5% prob → already priced in → discount |
| SKIP | `confidence × 0.5` | Low-signal, always halved |

Example: Headline entails "Fed will cut" for a market at 95% YES. Raw confidence 0.90 → scaled `0.90 × 0.05 = 0.045`. **Don't trade** — the market already knows.

## Dynamic Market Management

Markets default to **OFF**. Operators arm specific markets from the dashboard — only armed markets consume compute and generate trades.

- **Toggle:** Per-market agent toggle in the Markets panel
- **Server-authoritative:** Backend owns the `enabled_markets` set, validates all toggle commands
- **Tag-filter:** Armed markets only evaluate when story tags overlap with market tags
- **Visual feedback:** Unarmed markets dimmed at 30% opacity, header shows "X/Y armed"

At scale (5,000+ markets from on-chain registry), this is essential. You arm markets where you have informational edge, not all of them.

## Dashboard

Bloomberg Terminal-style real-time operations UI. 13 panels, all updating via WebSocket. Monospace font (JetBrains Mono), pure black background, CRT scanline overlay, zero border-radius.

| Panel | Purpose |
|---|---|
| **Terminal Header** | Connection status (WS/Kalshi/Polymarket/ONNX), throughput (ev/s, dec/s), hit rate, YES%, uptime, UTC clock |
| **Ticker Tape** | Auto-scrolling ribbon of latest decisions with action, confidence, latency |
| **News Wire** | Incoming headlines with urgency badges, sentiment, category tags, velocity |
| **Markets** | Armed/disarmed markets with probability, signal strength, action counts, sparklines |
| **Position Book** | Per-market YES/NO pressure bars, average confidence, simulated P&L |
| **Decision Feed** | Full decision details — action, confidence bar, latency, reasoning, source headline |
| **Tag Heatmap** | Category frequency distribution with intensity-scaled tiles |
| **Latency Chart** | Real-time per-decision latency line chart |
| **Throughput Chart** | Events/sec and decisions/sec area chart (120-point rolling window) |
| **Confidence Histogram** | Distribution across 5 buckets with mean (μ) and sample size |
| **Decision Distribution** | YES/NO/SKIP totals bar chart |
| **Latency Stats** | MIN / P50 / AVG / P95 / P99 / MAX with standard deviation |
| **System Bar** | Aggregate rates, action breakdowns, min/max latency, connection status |

## Getting Started

### Prerequisites

- Python 3.11+, Node.js 18+
- [Modal](https://modal.com) account (free tier works)
- Redis (live mode only)

### Setup

```bash
# 1. Server
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Modal
pip install modal
modal setup                              # authenticate (opens browser)
modal deploy agents/modal_app_fast.py    # deploy ONNX NLI agent (~2 min)

# 3. Frontend
cd client/client && npm install

# 4. Environment (live mode only)
cat > server/.env << 'EOF'
DBNEWS_USERNAME=...
DBNEWS_PASSWORD=...
DBNEWS_WS_URL=wss://dbws.io
REDIS_URL=redis://localhost:6379/0
EOF
```

### Run

```bash
./start.sh --mock    # demo mode — no external services, instant setup
./start.sh           # live mode — real news feed + Modal inference
```

Open **http://localhost:5173** — dashboard populates immediately.

### Verify Modal

```bash
cd server && python3 -c "
import modal, asyncio
agent = modal.Cls.from_name('trademaxxer-agents-fast', 'FastMarketAgent')()
result = asyncio.run(agent.evaluate_batch.remote.aio([
    {'headline': 'Fed raises rates 50bps', 'question': 'Will the Fed cut rates?',
     'probability': 0.5, 'market_address': 'test', 'story_id': 'test'}
]))
print(result)
"
```

## Infrastructure

```
VPS ($5/mo)                          Modal (pay per use)
├── News WebSocket client            └── ONNX NLI containers
├── Intake / tagger                      ├── buffer_containers=1 (always warm)
├── Direct dispatcher                    ├── scaledown_window=300s
├── Executor                             └── auto-scales 0→N
├── Position monitor
├── Market registry cache
├── WebSocket server
└── Redis (pub/sub + state)

Vercel (free)
└── React dashboard
```

| Component | Host | Monthly Cost |
|---|---|---|
| Server (news + dispatch + executor) | VPS | ~$5 |
| Redis | Local on VPS | $0 |
| ONNX NLI inference | Modal | ~$0.001/story |
| Dashboard | Vercel | $0 |
| **Total** | | **~$5–10/mo** |

For context: a single Groq API call at scale costs more per day than our entire monthly infrastructure.

## Tech Stack

**Built from scratch:**
- News ingestion pipeline — WebSocket client, normalizer, VADER tagger, category extraction
- NLI classification engine — ONNX Runtime inference, probability-aware confidence scaling, batched evaluation
- Direct dispatch system — tag-filtering, chunked parallel RPCs, fire-and-forget broadcasting
- Execution layer — decision validation, position management, risk controls
- Market registry — on-chain state indexing, tag-based market lookup
- Bloomberg Terminal dashboard — 13 real-time panels, WebSocket state management, CRT aesthetic
- Mock system — 100 headlines, simulated agents, full offline pipeline
- Single-command launcher (`start.sh`)

**Third-party:**
- [DeBERTa-v3-xsmall](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall) — pretrained NLI model (22M params)
- [ONNX Runtime](https://onnxruntime.ai/) — optimized CPU inference
- [Modal](https://modal.com) — serverless container orchestration
- [DBNews](https://dbnews.ai) — real-time financial news WebSocket feed
- [Redis](https://redis.io) — pub/sub messaging + state
- [VADER](https://github.com/cjhutto/vaderSentiment) — financial sentiment analysis
- [Recharts](https://recharts.org) — chart rendering
- React + Vite + Tailwind CSS — frontend

## Repo Structure

```
trademaxxer/
├── server/
│   ├── main.py                          # Orchestrator — news, dispatch, execution
│   ├── mock_feed.py                     # 100 headlines + mock evaluator
│   ├── requirements.txt
│   ├── news_streamer/
│   │   ├── config.py                    # Environment configuration
│   │   ├── models/news.py               # RawNewsItem, TaggedNewsItem
│   │   ├── dbnews_client/client.py      # DBNews WebSocket with auto-reconnect
│   │   ├── tagger/tagger.py             # Sentiment + category + ticker extraction
│   │   ├── ws_server/server.py          # WebSocket broadcast server
│   │   └── pubsub/                      # Redis pub/sub fan-out
│   ├── agents/
│   │   ├── schemas.py                   # MarketConfig, StoryPayload, Decision
│   │   ├── nli_postprocess.py           # NLI logits → action + confidence scaling
│   │   ├── modal_app_fast.py            # Modal ONNX NLI deployment
│   │   └── listener.py                  # Per-market Redis subscriber
│   └── pub_sub_feed/                    # Redis pub/sub library
├── client/client/
│   ├── src/
│   │   ├── App.jsx                      # 3-column Bloomberg Terminal layout
│   │   ├── index.css                    # Terminal theme + CRT animations
│   │   ├── hooks/useWebSocket.js        # State management + metrics
│   │   └── components/                  # 13 dashboard panels
│   └── package.json
├── start.sh                             # One-command launcher
├── ARCHITECTURE.md                      # Mermaid diagrams — all system flows
├── DEVLOG.md                            # Development log with benchmarks
└── README.md
```

## Development Log

Full technical narrative with benchmarks, architecture decisions, and war stories in [DEVLOG.md](DEVLOG.md).

System flow diagrams (mermaid) in [ARCHITECTURE.md](ARCHITECTURE.md).

## License

MIT
