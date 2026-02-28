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

## Session 4 — Groq → NLI Model Migration (Feb 28, 2026)

### Goal

Replace Groq API calls with a pretrained NLI model running directly on Modal. Eliminate external API dependency, eliminate rate limits, reduce inference latency.

### The Problem

Running live against DBNews with 4 markets, Groq's free tier rate limit (6000 TPM) was exhausted instantly. Every headline triggered 4 separate Groq API calls (one per market listener), burning ~280 tokens each. During high-volume news events (e.g. Iran situation), the feed was producing 2+ stories/sec — that's 8+ Groq calls/sec, way past the limit. Half the evaluations were failing with `429 Rate limit exceeded`.

Beyond rate limits, the per-call latency was 250–330ms for Groq inference alone, plus Modal RPC overhead. Total latency per decision was ~300–400ms warm, ~3s cold.

### The Solution

Replaced Groq with `cross-encoder/nli-deberta-v3-xsmall` — a pretrained Natural Language Inference model that frames classification as a premise-hypothesis entailment task:

- **Premise:** news headline
- **Hypothesis:** market question (e.g. "Will oil prices exceed $120/barrel before June 2026?")
- **Output:** entailment (YES) / contradiction (NO) / neutral (SKIP)

This is a 22M parameter DeBERTa model that runs entirely on CPU in ~10ms per batch.

### Architecture: What Changed

**Before (Groq):**
```
Story → Redis → Listener → Modal → Groq API → Decision
                                    ↑ 250ms + network
                                    ↑ rate limited
                                    ↑ separate call per market
```

**After (NLI):**
```
Story → Redis → Listener → Modal → NLI model → Decision
                                    ↑ ~10ms inference
                                    ↑ no rate limits
                                    ↑ batched (all markets in one call)
```

### New Files

- **`agents/modal_app_fast.py`** — New Modal app (`trademaxxer-agents-fast`). Downloads `cross-encoder/nli-deberta-v3-xsmall` from HuggingFace during image build (baked in, no download on cold start). `FastMarketAgent.evaluate_batch()` takes a list of items, tokenizes, runs a single forward pass, returns decisions.

- **`agents/nli_postprocess.py`** — Maps NLI logits to YES/NO/SKIP. Label order for this model: `0=contradiction→NO, 1=entailment→YES, 2=neutral→SKIP`. Includes probability-aware confidence scaling:
  - YES at 95% market prob → already priced in → confidence discounted
  - NO at 10% market prob → already priced in → confidence discounted
  - SKIP confidence halved (low-signal)

### Changes to Existing Files

- **`agents/listener.py`** — `_modal_evaluate()` now calls `trademaxxer-agents-fast` / `FastMarketAgent.evaluate_batch()` with a single-item batch instead of `trademaxxer-agents` / `MarketAgent.evaluate()`. No Groq, no secrets needed.

- **`main.py`** — Warmup now calls the NLI agent's `evaluate_batch` endpoint. Everything else (Redis, listeners, mock mode) unchanged.

### Obstacles

1. **ONNX export rabbit hole** — Initially tried exporting to ONNX + INT8 quantization for maximum speed. Hit HuggingFace cache permission errors in sandbox. Realized the complexity wasn't worth it: PyTorch inference on CPU for a 22M param model is already ~10ms. Scrapped ONNX, load straight from HuggingFace.

2. **Modal image build order** — `add_local_python_source()` must come last in the Modal image chain. Placing `.run_commands()` after it throws an error because Modal mounts local sources at runtime, not build time. Fixed by reordering: `pip_install → run_commands → add_local_python_source`.

3. **`.env` parsing** — The `.env` file had `========` header lines (not comments). `python-dotenv` couldn't parse them, so env vars never loaded. Changed to `#` prefixed comments.

4. **`python-dotenv` not installed** — The `try/except ImportError: pass` in `main.py` silently skipped loading `.env` entirely. Installed `python-dotenv` in venv.

5. **Groq rate limits** — The original trigger for this migration. Free tier: 6000 TPM. With 4 markets × 2+ stories/sec × ~280 tokens/call = way over budget. NLI model has zero external API calls, zero rate limits.

### Architecture Decisions

1. **HuggingFace direct load over ONNX** — Trading ~5ms of inference time for zero export complexity. The model is baked into the Modal image, so cold starts don't include a download. Warm inference is ~10ms vs ~5ms ONNX — not worth the maintenance burden.

2. **Keep Redis pub/sub** — Considered replacing Redis with in-process queues for lower latency. Kept Redis because it cleanly decouples the news tagger from agent listeners, supports future multi-process deployment, and the overhead is small (~1-2ms local).

3. **Batched endpoint** — `evaluate_batch()` accepts a list so a single Modal RPC can evaluate all markets. Currently each listener sends a 1-item batch, but the architecture is ready for true batching if we add a central dispatcher later.

---

## Session 5 — Launch Script (Feb 28, 2026)

### Goal

One command to start everything: Redis, server, frontend.

### Implementation

Created `start.sh` at project root:

```bash
./start.sh           # live: Redis + DBNews + Modal NLI agents
./start.sh --mock    # mock: fake news + fake agents (no Redis/Modal)
```

- Starts Redis (skipped in mock mode), Python server, and Vite dev server
- Traps SIGINT/SIGTERM to clean up all child processes
- Prints PIDs and dashboard URL
- Ctrl-C stops everything

---

## Session 6 — Sub-100ms Latency Overhaul (Feb 28, 2026)

### Goal

Cut news-to-decision latency from ~300–400ms to sub-100ms. The system must stay on Modal — no local inference fallback (yet). Every millisecond counts: we're competing with other bots reading the same headlines.

### The Problem: Where Was Time Going?

Profiled the warm-path latency at ~300–400ms. Breakdown:

```
Component                    Latency
─────────────────────────────────────
Tagger (VADER + regex)       ~5ms
Redis publish                ~3ms        ← unnecessary in hot path
Redis subscribe + pull       ~5–10ms     ← unnecessary in hot path
Modal .remote() RPC          ~100–260ms  ← network to cloud
PyTorch NLI inference        ~40–50ms    ← CPU, no optimization
WebSocket broadcast (await)  ~1–5ms      ← blocking
Modal handle init            ~2ms/call   ← re-created per call
─────────────────────────────────────
Total                        ~300–400ms
```

Two insights:
1. **Redis was in the hot path for no reason.** Tagger and inference run in the same process — publishing to Redis only to read it back from Redis is pure waste.
2. **PyTorch was overkill.** A 22M param model doesn't need gradient tracking, GPU kernels, or a 1.5GB runtime. ONNX Runtime on CPU is purpose-built for this.

### Phase 1: ONNX Runtime on Modal

Replaced PyTorch with ONNX Runtime in `modal_app_fast.py`:

- **Model:** Pre-exported `Xenova/nli-deberta-v3-xsmall` ONNX model from HuggingFace (no manual export, no torch dependency)
- **Runtime:** `onnxruntime` with `CPUExecutionProvider`
- **Image size:** ~300MB (down from ~1.5GB with PyTorch)
- **Dependencies:** `onnxruntime`, `transformers`, `numpy`, `huggingface_hub` — no `torch`
- **Image build:** Model + tokenizer downloaded during `run_commands()` and baked into the image — zero download on cold start

```python
# Before: PyTorch
tokens = self.tokenizer(..., return_tensors="pt")
with torch.no_grad():
    logits = self.model(**tokens).logits  # ~40-50ms

# After: ONNX Runtime
tokens = self.tokenizer(..., return_tensors="np")
logits = self.session.run(None, {
    "input_ids": tokens["input_ids"],
    "attention_mask": tokens["attention_mask"],
})[0]  # ~5-15ms
```

**Result:** Inference dropped from **~40–50ms** to **~5–15ms** per batch. Image builds are faster too.

### Phase 2: Kill Redis in the Hot Path (Direct Dispatch)

Eliminated the entire Redis pub/sub round-trip for agent evaluation. The old flow:

```
news → tagger → Redis publish → Redis subscribe → listener → Modal RPC
```

The new flow:

```
news → tagger → direct dispatch → Modal RPC
```

Implemented `_nli_eval_and_broadcast()` in `main.py`:

1. **Tag-filter:** For each incoming story, intersect `story.tags` with each market's `tags`. Only matching + enabled markets proceed.
2. **Chunk:** Split matching markets into batches of `BATCH_SIZE=50`.
3. **Parallel RPCs:** Fire all chunks simultaneously with `asyncio.gather()`. Modal spins up containers as needed — each chunk is one RPC.
4. **Fan out results:** Each result is broadcast to the dashboard via fire-and-forget `asyncio.create_task()`.

This is the key scalability unlock. With 5,000 markets and a batch size of 50, that's 100 parallel RPCs — but they all run in the same wall-clock time as a single one. Modal handles the horizontal scaling.

Redis is still in the codebase for decoupling (future multi-process deployment) but it's no longer on the critical path.

### Phase 3: Fire-and-Forget Everything Non-Critical

Every `await` that wasn't strictly necessary was converted to `asyncio.create_task()`:

```python
# Before: blocking — inference waits for WS broadcast
await ws_server.broadcast(news, tagged)

# After: fire-and-forget — inference doesn't wait
asyncio.create_task(ws_server.broadcast(news, tagged))
```

Applied to:
- News broadcast to dashboard
- Decision broadcast to dashboard
- Market state updates

This ensures the only `await` in the hot path is the Modal RPC itself.

### Phase 4: Singleton Modal Handle

Previously, `_get_fast_agent()` or `modal.Cls.from_name()` was called on every evaluation. Now it's a module-level singleton initialized once:

```python
_fast_agent = None

def _get_fast_agent():
    global _fast_agent
    if _fast_agent is None:
        Cls = modal.Cls.from_name("trademaxxer-agents-fast", "FastMarketAgent")
        _fast_agent = Cls()
    return _fast_agent
```

Saves ~2ms per call. Small, but when you're chasing milliseconds, it adds up.

### Benchmarks

Deployed and tested with 5 back-to-back warm calls (batch of 3 items each):

| Call | ONNX Inference | Modal RPC Overhead | Total |
|------|---------------|--------------------|-------|
| 1 (warm) | 41ms | 264ms | 305ms |
| 2 | 40ms | 145ms | 186ms |
| 3 | 34ms | 108ms | 143ms |
| 4 | 40ms | 161ms | 200ms |
| 5 | 37ms | 107ms | 144ms |

**Steady-state (warm, local Mac):** ~143–200ms total, ~34–41ms inference, ~107–264ms RPC overhead.

The bottleneck is now entirely **network latency from the local machine to Modal's cloud** (~100–260ms depending on congestion). The inference itself is ~35ms.

### The Network Wall

On a consumer Mac over residential internet, sub-100ms to Modal is physically impossible. The speed of light from a home in CA to Modal's AWS region is ~30ms one-way minimum, and Modal's internal routing adds more.

**Projected latency on a co-located VPS:**

```
Component              Local Mac     VPS (same region)
───────────────────────────────────────────────────────
ONNX inference         ~35ms         ~35ms
Modal RPC overhead     ~100-260ms    ~30-50ms
Total                  ~143-305ms    ~65-85ms  ✓
```

A $5/mo VPS in US-East (same region as Modal's infra) would bring total latency to **~65–85ms**, comfortably under 100ms.

### Obstacles

1. **ONNX export rabbit hole (revisited)** — Initially tried to export the model to ONNX locally. Hit HuggingFace cache permission errors. Realized Xenova already publishes a pre-exported ONNX version on HuggingFace. Just `hf_hub_download()` it. Zero friction.

2. **Modal image build order (again)** — `add_local_python_source()` must come LAST. Placing `run_commands()` after it fails because Modal mounts local sources at runtime, not build time. The image chain must be: `pip_install → run_commands → add_local_python_source`.

3. **Batch size tuning** — Too small (1) = too many RPCs. Too large (1000) = tokenizer OOM on a single container. 50 is the sweet spot: fits in memory, amortizes RPC overhead, still parallelizable.

### Architecture Decisions

1. **ONNX over PyTorch** — 3–4x faster inference, 5x smaller image. The model is frozen (no fine-tuning needed), so we don't need autograd. ONNX Runtime is the right tool for pure inference.

2. **Direct dispatch over Redis** — Same-process communication should be in-process. Redis is for cross-process decoupling, not for calling yourself. Saved ~10–15ms per decision.

3. **Chunked parallel batching** — Scales to any number of markets. 12 markets = 1 chunk = 1 RPC. 5,000 markets with 50-overlap = 100 parallel RPCs, same wall-clock time. Modal's auto-scaling handles the containers.

4. **Fire-and-forget WS broadcasts** — Dashboard updates are cosmetic, not latency-critical. Blocking on them in the hot path was wasting 1–5ms per decision for no reason.

---

## Session 7 — Dynamic Market Management (Feb 28, 2026)

### Goal

Let users toggle which markets are actively monitored from the dashboard. Markets should default to OFF — the system doesn't burn compute until the user explicitly arms a market.

### The Problem

Previously, all hardcoded `test_markets` were always active. Every news story triggered evaluations for every market. Wasteful when you only care about 3 out of 12 markets. And when we scale to 5,000 markets from a real registry, evaluating all of them on every headline would be insane.

### Implementation

**Backend (`main.py`):**
- `enabled_markets: set[str]` tracks which market addresses are active. Starts empty.
- `_handle_command(data)` processes `toggle_market` messages from the UI.
- `on_news()` only evaluates enabled markets (tag-filter intersects `enabled_markets`).
- Market state is broadcast to all clients whenever a toggle happens.
- New clients receive current market state in the welcome message.

**WebSocket server (`ws_server/server.py`):**
- Added `set_command_handler()` — registers a callback for client-to-server messages.
- Added `set_welcome_extra()` — injects market state into the initial handshake.
- Added `broadcast_json()` — sends arbitrary payloads (used for `markets_state`).
- Client message handling: parses incoming JSON, routes `toggle_market` to the handler.

**Frontend (`useWebSocket.js`):**
- `enabledMarkets` state (Set) tracks which markets the user has armed.
- `toggleMarket(address)` sends `{type: "toggle_market", address, enabled}` to the server.
- Handles `markets_state` messages from server to sync state.

**UI (`MarketGrid.jsx`):**
- New `AgentToggle` component — Bloomberg-style toggle button per market row.
- Disabled markets are visually dimmed (`opacity-30`).
- Header shows "X/Y armed" count.
- Toggle click sends command to server → server updates state → broadcasts to all clients → UI re-renders.

### Architecture Decisions

1. **Server-authoritative state** — The backend owns `enabled_markets`. The UI sends a request, the server validates and broadcasts the new state. No split-brain.

2. **All markets OFF by default** — Forces intentional market selection. When we scale to 5,000 markets, users will arm specific markets they have edge on, not all of them.

3. **Tag-filter comes after enable-filter** — `_nli_eval_and_broadcast()` first checks `enabled_markets`, then checks tag overlap. This means an armed market only gets evaluated if the story is actually relevant.

---

## Session 8 — Future Latency Ideas (Feb 28, 2026)

### Creative Approaches Considered

With Modal RPC being the floor (~100ms from a Mac, ~30–50ms from a VPS), we brainstormed creative ways to push further:

1. **Move the entire server onto Modal** — Run news streamer, tagger, AND inference all in a single Modal container. Inference becomes an in-process function call (~35ms, zero RPC). The Mac only receives final decisions for the UI over WebSocket. This is the nuclear option.

2. **`@modal.asgi_app()` persistent endpoint** — Deploy inference as a FastAPI server on Modal with keep-alive HTTP/2 connections. Bypasses Modal's `.remote()` scheduling layer. Could save 20–50ms by avoiding per-call container scheduling.

3. **Persistent WebSocket bridge** — Open a long-lived WebSocket between the VPS and a Modal container. Push headlines in, receive decisions back — no per-call connection setup.

### What's Next

- [x] True batching: chunked parallel RPCs (done — Session 6)
- [x] Dynamic market management: UI toggle (done — Session 7)
- [ ] Deploy server on co-located VPS (est. savings: 80–200ms)
- [ ] Move entire pipeline to Modal (est. total latency: ~40ms)
- [ ] `--local-inference` flag: run NLI model locally when Modal RPC exceeds budget
- [ ] Per-stage timing instrumentation (tagger → dispatch → Modal → decision)
- [ ] Market registry in Redis (replace hardcoded `MarketConfig`)
- [ ] Decision queue (decouple agents from executor)
- [ ] Solana executor — read decisions, fire trades via proprietary API
- [ ] Position monitor — resolution, edge compression, contradicting news, time decay
- [ ] P&L tracking from real trades (replace simulated P&L)
