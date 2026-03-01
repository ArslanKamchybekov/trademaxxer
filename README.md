# TradeMaxxer

**Autonomous news-to-trade pipeline for prediction markets on Solana.**

Breaking news hits the wire. Our agents read it, reprice every relevant market, and execute trades via Jupiter Ultra on Solana. End-to-end in under 1 second. No human in the loop.

---

<p align="center">

**68ms** fastest decision · **20x** parallel market evals · **32 tokens** per inference · **<1s** news to trade · **Bloomberg Terminal** UI

</p>

---

## The Problem

Prediction markets reprice based on real-world news. The window between a headline hitting the wire and the market adjusting is seconds. Manual traders can't read, evaluate, and execute fast enough. By the time a human places a trade, the edge is gone.

## Our Approach

TradeMaxxer is a fully autonomous pipeline that ingests live news, fans out AI evaluations across all relevant markets in parallel, and executes trades on Solana via Jupiter Ultra routing.

**Core loop:**
1. News headline arrives via WebSocket
2. Tagger classifies topic + urgency in ~5ms
3. Redis routes it only to relevant markets
4. Modal spins up parallel Groq evaluations across all matching markets
5. Each agent returns YES/NO/SKIP + a theoretical fair price in 32 JSON tokens
6. Decisions with edge > 6% trigger Jupiter Ultra swaps on Solana
7. Portfolio updates in real-time on the Bloomberg Terminal dashboard

## Architecture

```
WorldMonitor WS ──→ Tagger ──→ Redis Pub/Sub ──→ Modal Fan-Out ──→ Groq LLM ──→ Decision ──→ Jupiter Ultra ──→ Solana TX
  ~0ms         ~5ms         <1ms             20× parallel      68ms fastest    6% threshold    ~85ms quote      ~400ms confirm
                                                                                    │
                                                                              ┌─────┴─────┐
                                                                           Kalshi       Dashboard
                                                                        (market registry)  (real-time UI)
```

| Component | What it does | Latency |
|---|---|---|
| **WorldMonitor WebSocket** | Persistent connection to Reuters, AP, Bloomberg feeds (~2 stories/sec) | Real-time stream |
| **Tagger** | VADER sentiment + regex category extraction + keyword tagging | ~5ms |
| **Redis Pub/Sub** | Tag-based fan-out. Markets subscribe only to relevant topic channels | <1ms |
| **Modal Fan-Out** | Serverless containers evaluate all matching markets in parallel via `asyncio.gather()` | 20x concurrency |
| **Groq LLM** | Llama 3.1 8B Instant. 32 JSON tokens: `{action, p}`. Temp 0.1, timeout 2s | 68ms fastest, ~250ms avg |
| **Decision Engine** | Computes theoretical price. Skips if \|theo - current\| < 6%. Confidence = delta x 2 | <1ms |
| **Jupiter Ultra** | Routes USDC/SOL swaps across Raydium, Orca pools for optimal execution | ~85ms quote |
| **Solana TX** | On-chain swap confirmation in one slot | ~400ms |
| **Kalshi Registry** | Fetches live prediction markets + streams orderbook prices via WebSocket | REST + WS |
| **Dashboard** | Bloomberg Terminal UI. 13 panels, real-time WebSocket, CRT aesthetic | <16ms render |

## How a Trade Happens

```
t=0ms      Reuters wire: "Iran strikes Israeli military base in Negev"
t=5ms      Tagger: categories [geopolitics, politics], urgency HIGH
t=6ms      Redis: routed to 3/20 matching markets
t=6ms      Modal: 3 Groq evals fired in parallel via asyncio.gather()
t=340ms    Groq returns: {action: "YES", p: 91} for "Iran Strike" market
t=341ms    Decision: theo=0.91, current=0.82, delta=0.09 > 0.06 threshold → TRADE
t=341ms    Dashboard updated (fire-and-forget)
t=426ms    Jupiter Ultra: USDC → SOL quote via Raydium
t=826ms    Solana TX confirmed on-chain
```

**68ms fastest decision. 340ms typical. <1s news to trade.**

## Key Optimizations

| Optimization | Impact | How |
|---|---|---|
| **Modal Serverless Fan-Out** | 20x parallel evals, same wall-clock | `asyncio.gather()` across all matching markets on auto-scaling containers |
| **Groq 32-Token Inference** | 68ms fastest decision | Minimal JSON output: just action + probability. No verbose reasoning. |
| **Jupiter Ultra Routing** | Optimal swap execution | Routes across Solana DEX liquidity pools for best price |
| **Tag-Based Pub/Sub** | ~80% irrelevant pairs dropped | Redis routes headlines by topic. Agents only see news they care about |
| **Fire-and-forget broadcasts** | -5ms per decision | `asyncio.create_task()` for all non-critical I/O |
| **Singleton Modal handle** | -2ms per call | Module-level agent reference, initialized once |

## Dashboard

Bloomberg Terminal-style real-time operations UI. Monospace font (JetBrains Mono), pure black background, CRT scanline overlay, zero border-radius.

| Panel | Purpose |
|---|---|
| **Terminal Header** | Connection status, throughput (ev/s, dec/s), hit rate, uptime, UTC clock |
| **Ticker Tape** | Auto-scrolling ribbon of latest decisions |
| **News Wire** | Incoming headlines with urgency, sentiment, tags |
| **Markets** | Armed/disarmed markets with probability, signal strength, agent toggles |
| **Solana Wallet** | Portfolio value, P&L, USDC balance, Jupiter swap history, contract count |
| **Decision Feed** | Full decision details with theo price, confidence, latency |
| **Tag Heatmap** | Category frequency with intensity-scaled tiles |
| **Latency Chart** | Real-time per-decision latency |
| **Throughput Chart** | Events/sec and decisions/sec (120-point rolling window) |
| **Confidence Histogram** | Distribution with mean and sample size |
| **Decision Distribution** | YES/NO/SKIP bar chart |
| **Latency Stats** | MIN / P50 / AVG / P95 / P99 / MAX |
| **System Bar** | Aggregate rates, action breakdowns, connection status |

## Demo Mode

TradeMaxxer ships with a full demo system that runs without any external API keys:

- **7 demo contracts** modeled after Kalshi markets (Iran strike, Fed rate cut, Bitcoin $150k, etc.)
- **~40 synthetic headlines** injected every 8-25 seconds covering geopolitics, oil, Fed, crypto, VIX
- **Mock agents** return randomized YES/NO/SKIP decisions with realistic latency
- **Jupiter wallet** simulates USDC/SOL swaps and portfolio tracking

```bash
./start.sh --mock    # everything runs locally, zero dependencies
```

## Presentation

Interactive Reveal.js presentation in the `presentation/` folder with:

- Bloomberg Terminal aesthetic matching the dashboard
- Animated charts and visualizations (Framer Motion + Recharts)
- Interactive architecture flow (click nodes for details)
- Fintech/Simple mode toggle for audience adaptation
- Prediction markets explainer slide

```bash
cd presentation && pnpm dev --port 5174
```

## Getting Started

### Prerequisites

- Python 3.11+, Node.js 18+, pnpm
- [Modal](https://modal.com) account (free tier works)
- [Groq](https://groq.com) API key
- Redis (live mode only)

### Setup

```bash
# Server
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Modal
pip install modal
modal setup
modal deploy agents/modal_app.py

# Frontend
cd client/client && pnpm install

# Presentation (optional)
cd presentation && pnpm install

# Environment (live mode only)
cat > server/.env << 'EOF'
WORLDMONITOR_USERNAME=...
WORLDMONITOR_PASSWORD=...
WORLDMONITOR_WS_URL=wss://worldmonitor.io
GROQ_API_KEY=...
REDIS_URL=redis://localhost:6379/0
EOF
```

### Run

```bash
./start.sh --mock    # demo mode: no external services needed
./start.sh --local   # live news + local Groq inference
./start.sh           # live news + Modal cloud inference
```

Dashboard: **http://localhost:5173**

## Tech Stack

**Built from scratch:**
- News ingestion pipeline: WebSocket client, normalizer, VADER tagger, category extraction
- Agent evaluation: Groq LLM classification, probability-aware confidence scaling, parallel fan-out
- Direct dispatch: tag-filtering, chunked parallel RPCs, fire-and-forget broadcasting
- Solana wallet: Jupiter Ultra API integration, USDC/SOL swap simulation, portfolio tracking
- Market registry: Kalshi API integration, tag-based market lookup, live price streaming
- Bloomberg Terminal dashboard: 13 real-time panels, WebSocket state management, CRT aesthetic
- Demo system: 7 contracts, 40 headlines, mock agents, synthetic injector
- Reveal.js presentation: animated slides, interactive architecture, fintech mode toggle
- Single-command launcher (`start.sh`)

**Third-party:**
- [Groq](https://groq.com) + Llama 3.1 8B Instant: LLM inference
- [Modal](https://modal.com): serverless container orchestration
- [Jupiter Ultra API](https://station.jup.ag/docs/ultra): Solana DEX aggregation
- [WorldMonitor](https://worldmonitor.io): real-time financial news WebSocket
- [Kalshi](https://kalshi.com): prediction market data + live prices
- [Redis](https://redis.io): pub/sub messaging
- [VADER](https://github.com/cjhutto/vaderSentiment): financial sentiment
- React + Vite: frontend
- Reveal.js + Framer Motion + Recharts: presentation

## Repo Structure

```
trademaxxer/
├── server/
│   ├── main.py                          # Orchestrator: news, dispatch, execution
│   ├── demo_markets.py                  # 7 demo contracts + synthetic headline injector
│   ├── mock_feed.py                     # Mock headlines + mock evaluator
│   ├── requirements.txt
│   ├── news_streamer/
│   │   ├── config.py                    # Environment configuration
│   │   ├── models/news.py               # RawNewsItem, TaggedNewsItem
│   │   ├── dbnews_client/client.py      # WorldMonitor WebSocket with auto-reconnect
│   │   ├── tagger/tagger.py             # Sentiment + category + ticker extraction
│   │   ├── ws_server/server.py          # WebSocket broadcast server
│   │   └── pubsub/                      # Redis pub/sub fan-out
│   ├── agents/
│   │   ├── agent_logic.py               # Core evaluate(): news + market → Groq → decision
│   │   ├── schemas.py                   # MarketConfig, StoryPayload, Decision
│   │   ├── prompts.py                   # v6 prompt: 32-token JSON output
│   │   ├── groq_client.py              # Async Groq wrapper (llama-3.1-8b-instant)
│   │   ├── modal_app.py                # Modal deployment (MarketAgent)
│   │   └── listener.py                  # Per-market Redis subscriber
│   └── market_registry/
│       ├── kalshi.py                    # Kalshi REST API: events → MarketConfig
│       └── kalshi_ws.py                 # Kalshi WebSocket: live orderbook prices
├── client/client/
│   ├── src/
│   │   ├── App.jsx                      # 3-column Bloomberg Terminal layout
│   │   ├── index.css                    # Terminal theme + CRT animations
│   │   ├── hooks/useWebSocket.js        # State management + metrics
│   │   └── components/
│   │       ├── SolanaWallet.jsx         # Jupiter Ultra swaps, portfolio, P&L
│   │       ├── MarketGrid.jsx           # Market toggles + signal strength
│   │       ├── DecisionFeed.jsx         # Agent decisions with theo prices
│   │       ├── OrderTicket.jsx          # Manual order entry
│   │       ├── PositionBook.jsx         # Combined positions
│   │       └── ModalAgentPanel.jsx      # Agent stats panel
│   └── package.json
├── presentation/
│   ├── src/
│   │   ├── App.jsx                      # Reveal.js slides (7 sections)
│   │   └── index.css                    # Bloomberg Terminal presentation theme
│   └── package.json
├── start.sh                             # One-command launcher
├── ARCHITECTURE.md                      # System flow diagrams
├── DEVLOG.md                            # Development log with benchmarks
└── README.md
```

## Team

- **Anirudh Kuppili** · Eng. @ Aparavi (Series A)
- **Arslan Kamchybekov** · Founding Eng. @ Kairos (backed by Geneva Trading & a16z)
- **Mathew Randal** · Eng. @ Optiver, Quant @ Illinois

## License

MIT
