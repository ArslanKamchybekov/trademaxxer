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

Designed the stream layer as Python `Protocol` classes so external bindings can be plugged in without touching agent code:

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

2. **Protocol-based stream abstraction** — The stream layer uses `typing.Protocol` so any binding just needs to implement `subscribe()`, `publish()`, and `ack()`. No inheritance required.

3. **Frozen dataclasses with dict serialization** — Modal requires serializable inputs/outputs. Using `to_dict()`/`from_dict()` on frozen dataclasses keeps the contract strict and debuggable. Every `Decision` carries `prompt_version` for traceability.

4. **Prompt version tracking** — Every decision records which prompt version produced it. When we A/B test prompts, we can attribute performance to the exact template.

5. **Buffer containers** — `buffer_containers=1` keeps one Modal container pre-warmed at all times. Costs a few cents/day but eliminates cold starts during trading hours.

---

## Session 2 — Redis Pub/Sub + Warm-up + Mock System (Feb 28, 2026)

### Goal

Wire the full pipeline end-to-end: news → Redis Pub/Sub → agent listeners → Modal → dashboard. Add a Modal warm-up call and a complete mock system for offline development.

### Phase 1: Redis Pub/Sub Integration

Originally planned as C++ Redis Streams with pybind11, but a Python `pub_sub_feed` library (`FeedPublisher` / `FeedSubscriber`) arrived and was adopted. It uses Redis Pub/Sub (not Streams) with tag-based fan-out and a pull-based API.

**Channel scheme:**
- `news:all` — every tagged story (fallback channel)
- `news:category:macro` — stories tagged `macro`
- `news:category:geopolitics` — stories tagged `geopolitics`
- etc.

**Publisher side** (`NewsPublisher` in `news_streamer/pubsub/`):
- Serializes `TaggedNewsItem` to a wire dict (camelCase keys)
- Publishes to `news:all` + each `news:category:{cat}` channel

**Subscriber side** (`AgentListener` in `agents/listener.py`):
- Each listener subscribes to `news:all` + its market's tag-specific channels
- Uses a `seen` set for deduplication (same story arrives on `news:all` and `news:category:macro`)
- Pull-based loop: `await sub.pull(timeout=1.0)`

**Key fix:** Initially listeners weren't firing because the tagger was too sparse — it didn't assign `geopolitics` or `politics` categories to most headlines. Fixed by subscribing every listener to `news:all` as a fallback, ensuring all news reaches all agents. Dedup handles the overlap.

### Phase 2: Modal Warm-up

Added `_warmup_modal()` to `main.py` — fires a dummy evaluation at startup to force a Modal container boot before real news arrives. This prevents the first real trade from eating a ~3s cold start penalty.

```python
async def _warmup_modal(market: MarketConfig) -> None:
    dummy = StoryPayload(id="warmup-ping", headline="warmup ping — ignore", ...)
    agent = modal.Cls.from_name("trademaxxer-agents", "MarketAgent")()
    await agent.evaluate.remote.aio(dummy.to_dict(), market.to_dict())
```

Runs after Redis connects, before news feed starts. Non-fatal on failure.

### Phase 3: Mock News Feed

Created `mock_feed.py` with 100 realistic financial/geopolitical headlines:
- Each headline has a body and pre-tagged categories
- Covers: geopolitics, politics, macro, economic_data, commodities, crypto, tech, earnings
- `run_mock_feed()` fires them at random 1–4s intervals through the same `on_news` callback as DBNews
- Activated via `python3 main.py --mock`

### Phase 4: Mock Agent Evaluator

Added `mock_evaluate()` to `mock_feed.py` — drop-in replacement for the Modal agent:
- Returns random YES (35%) / NO (30%) / SKIP (35%) decisions
- Confidence: 0.55–0.95 for YES, 0.50–0.90 for NO, 0.10–0.50 for SKIP
- Simulated latency: 150–400ms (realistic Groq range)
- Canned reasoning strings per action type
- `prompt_version: "mock"`

When `--mock` is active:
- Redis and Modal are skipped entirely
- The `on_news` callback runs mock evaluations inline (no pub/sub needed)
- Each headline generates 4 decisions (one per test market) immediately
- All decisions broadcast to dashboard via WebSocket

### Phase 5: WebSocket Decision Broadcasting

Added `broadcast_decision(data)` to `NewsWebSocketServer`:
- Sends `{"type": "decision", "data": {...}}` to all connected clients
- Agent listeners pass an `on_decision` callback that calls `ws_server.broadcast_decision()`
- Decision payloads enriched with `headline` and `market_question` for dashboard display

### Architecture Decisions

1. **Redis Pub/Sub over Redis Streams** — The `pub_sub_feed` library uses Pub/Sub, not Streams. For our use case (fan-out to multiple listeners, no persistent replay needed), Pub/Sub is simpler. If we need replay/persistence later, we can switch to Streams.

2. **Injectable evaluate_fn** — `AgentListener` accepts an `evaluate_fn` parameter (defaults to `_modal_evaluate`). This lets us swap in `mock_evaluate` or any other evaluator without changing the listener code.

3. **Inline mock agents** — In mock mode, agents run inside the `on_news` callback as fire-and-forget `asyncio.create_task()` calls. No Redis roundtrip, no pub/sub — just direct function calls. This keeps mock mode truly zero-dependency.

4. **news:all fallback** — Every listener subscribes to `news:all` regardless of its market's tags. This guarantees all news reaches all agents even if the tagger doesn't produce a matching category. Dedup via `seen` set prevents double-processing.

---

## Session 3 — Bloomberg Terminal Dashboard (Feb 28, 2026)

### Goal

Build a dense, real-time Bloomberg Terminal-style dashboard showing all system data with maximum data density.

### Design Language

- **Pure black** background (`#0a0a0a`)
- **Amber** (`#ff9800`) for headers, labels, latency numbers
- **Green** (`#00c853`) for YES, bullish, positive
- **Red** (`#ff1744`) for NO, bearish, negative
- **Monospace** font (JetBrains Mono) everywhere
- **Zero border-radius** — all sharp corners
- **1px borders** (`#1e1e1e`) — barely visible grid
- **CRT scanline overlay** — subtle repeating gradient
- Tabular-nums for all numeric displays

### Phase 1: WebSocket Hook

Rewrote `useWebSocket.js` to track rich metrics:
- Events + decisions counts, YES/NO/SKIP breakdowns
- Rolling latency array (last 200 samples) for percentile calculations
- Rolling confidence array (last 500 samples) for histogram
- Per-market stats: action counts, avg confidence, P&L simulation, confidence/latency sparkline data
- Per-tag counts for heatmap
- Throughput sampling: events/sec and decisions/sec counters reset every 1s
- News velocity sampling: events per 5-second window, polled every 2s
- Session start timestamp for uptime calculation

### Phase 2: New Components (6 added)

1. **TickerTape** — horizontally scrolling ribbon of latest 40 decisions. Infinite CSS animation (30s loop), pauses on hover. Shows action, truncated address, confidence, latency. Duplicated items for seamless looping.

2. **ThroughputChart** — Recharts `AreaChart` with two series: amber for events/sec, green for decisions/sec. Sampled every second, 120-point rolling window.

3. **ConfidenceHistogram** — Recharts `BarChart` bucketing confidence values into 5 ranges (0-20, 20-40, 40-60, 60-80, 80-100). Gradient amber coloring. Shows mean (μ) and sample size (n).

4. **TagHeatmap** — Category tiles sorted by frequency. Background intensity scales with count relative to max. Shows count and percentage per tag.

5. **PositionBook** — Per-market table with:
   - YES/NO pressure bars (proportional width)
   - Average confidence
   - Confidence micro-sparklines (inline SVG polyline)
   - Simulated P&L (YES: +conf*100, NO: -conf*50)
   - Total simulated P&L in header

6. **LatencyStats** — Percentile breakdown (MIN/P50/AVG/P95/P99/MAX) with horizontal bar visualization. Shows standard deviation (σ) and range.

### Phase 3: Enhanced Components (5 upgraded)

1. **TerminalHeader** — Added GROQ status dot, throughput rates (e/s, d/s), hit rate (non-skip %), YES%, uptime counter, millisecond-precision UTC clock.

2. **MarketGrid** — Added signal strength bars (5-bar indicator based on total signals), average confidence column, latency micro-sparklines per market.

3. **NewsTape** — Added row numbers, age timestamps (e.g. "12s"), news velocity display (items/s), 3 category tags per item.

4. **DecisionFeed** — Added row numbers, prompt version badge, source headline reference, age timestamps, wider confidence bars.

5. **SystemBar** — Added decision rate/s, Y%/N%/S% breakdowns, min/max latency, LIVE/IDLE status indicator.

### Phase 4: Layout

3-column layout fitting all 13 panels:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ TRADEMAXXER  WS·REDIS·MODAL·GROQ  EV 142  DEC 568  e/s 1  d/s 4  ... │
├─────────────────────────────────────────────────────────────────────────┤
│ TAPE │ YES FakeCo.. 78% 234ms │ NO FakeCo.. 62% 301ms │ ...          │
├──────────────┬──────────────────┬────────────────────────────────────────┤
│              │ MARKETS          │ AGENT DECISIONS                       │
│              │ prob sig Y N S.. │ YES ████ 78% 234ms mock              │
│ NEWS WIRE    │──────────────────│ → Direct positive signal...           │
│ 14:23:01 ... │ POSITION BOOK   │ ▸ Fed raises rates...                 │
│ 14:22:58 ... │ pressure  P&L   │────────────────────────────────────────│
│ 14:22:55 ... │──────────────────│ LATENCY     │ CONFIDENCE              │
│ 14:22:51 ... │ CATEGORIES      │ ───chart──── │ ───histogram────        │
│              │ macro 42  14.2% │─────────────┤─────────────────────────│
│              │ geo   38  12.8% │ THROUGHPUT   │ DISTRIBUTION │ LAT STAT │
│              │ crypto 28  9.4% │ ───chart──── │ ──bar chart──│ P50 245  │
├──────────────┴──────────────────┴──────────────┴──────────────┴──────────┤
│ CONNECTED │ EV 142  DEC 568  RATE 1.42/s │ Y 198 N 172 S 198 │ ...    │
└─────────────────────────────────────────────────────────────────────────┘
```

### CSS Animations

- `flash-news` — amber background flash on new news items (1.2s ease-out)
- `flash-decision-yes` / `flash-decision-no` — green/red flash on new decisions
- `ticker-scroll` — 30s infinite linear horizontal scroll for ticker tape
- `ticker-item` — subtle opacity pulse on individual ticker items
- `blink` — cursor blink for loading states ("Awaiting signals_")
- `body::after` — CRT scanline overlay (4px repeating gradient, 3% opacity)

### Performance Decisions

- All Recharts components use `isAnimationActive={false}` to prevent re-render stuttering
- Micro-sparklines are raw SVG polylines (no library, <1ms render)
- Rolling arrays capped (200 latency, 500 confidence, 120 throughput, 60 velocity)
- News and decision lists capped at 200 items with prepend + slice
- Throughput counter uses `useRef` to avoid re-renders on every tick

---

## What's Next

- [ ] Market registry in Redis (replace hardcoded `MarketConfig`)
- [ ] Decision queue (decouple agents from executor)
- [ ] Solana executor — read decisions, fire trades via proprietary API
- [ ] Position monitor — resolution, edge compression, contradicting news, time decay
- [ ] Prompt v4 — structured few-shot examples for borderline cases
- [ ] Multi-market live test (spawn N listeners, measure parallel throughput)
- [ ] P&L tracking from real trades (replace simulated P&L)
