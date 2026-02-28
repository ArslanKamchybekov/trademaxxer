# TradeMaxxer — Architecture & Flow Diagrams

Visual reference for every system flow, optimization decision, and data path. All diagrams are Mermaid — render them on GitHub, VS Code, or any Markdown viewer.

---

## 1. System Overview

```mermaid
graph TB
    subgraph Internet["External"]
        DB["DBNews WebSocket<br/>~2 stories/sec"]
        MODAL["Modal Cloud<br/>ONNX NLI Containers"]
    end

    subgraph VPS["Server (single Python process)"]
        NEWS["News Streamer"]
        TAG["Tagger<br/>(VADER + regex)"]
        DISP["Direct Dispatcher<br/>(tag-filter + chunk)"]
        WS["WebSocket Server"]
        MOCK["Mock Feed<br/>(100 headlines)"]
    end

    subgraph Client["Browser"]
        DASH["Bloomberg Terminal<br/>Dashboard"]
    end

    DB -->|WebSocket| NEWS
    MOCK -.->|--mock flag| NEWS
    NEWS -->|raw story| TAG
    TAG -->|tagged story| DISP
    DISP -->|batch RPC| MODAL
    MODAL -->|decisions| DISP
    DISP -->|fire-and-forget| WS
    TAG -->|fire-and-forget| WS
    WS <-->|WebSocket| DASH
    DASH -->|toggle_market| WS
```

---

## 2. Latency Evolution — Before & After

### v1-v3: Groq LLM Era (~300-660ms)

```mermaid
graph LR
    A["News arrives<br/>t=0ms"] --> B["Tagger<br/>+5ms"]
    B --> C["Redis publish<br/>+3ms"]
    C --> D["Redis subscribe<br/>+5ms"]
    D --> E["Modal RPC<br/>+80ms"]
    E --> F["Groq API call<br/>+250ms"]
    F --> G["Parse response<br/>+2ms"]
    G --> H["await WS broadcast<br/>+5ms"]
    H --> I["Decision delivered<br/>t≈350ms"]

    style C fill:#ff4444,color:#fff
    style D fill:#ff4444,color:#fff
    style F fill:#ff4444,color:#fff
    style H fill:#ff8844,color:#fff
```

### v5 (Modal ONNX): Direct Dispatch (~143ms local, ~85ms VPS)

```mermaid
graph LR
    A["News arrives<br/>t=0ms"] --> B["Tagger<br/>+5ms"]
    B --> C["Tag-filter + chunk<br/>+1ms"]
    C --> D["Modal RPC<br/>+100ms"]
    D --> E["ONNX inference<br/>+35ms"]
    E --> F["Postprocess<br/>+2ms"]
    F --> G["async WS broadcast<br/>+0ms (non-blocking)"]
    G --> H["Decision delivered<br/>t≈143ms"]

    style C fill:#00aa44,color:#fff
    style E fill:#00aa44,color:#fff
    style G fill:#00aa44,color:#fff
```

### v6 (current): Local ONNX — 16–69ms

```mermaid
graph LR
    A["News arrives<br/>t=0ms"] --> B["Tagger<br/>+5ms"]
    B --> C["Tag-filter + chunk<br/>+1ms"]
    C --> D["Local ONNX inference<br/>+10-35ms"]
    D --> E["Postprocess<br/>+1ms"]
    E --> F["async WS broadcast<br/>+0ms (non-blocking)"]
    F --> G["Decision delivered<br/>t≈16-69ms"]

    style C fill:#00aa44,color:#fff
    style D fill:#00ff44,color:#000
    style F fill:#00aa44,color:#fff
    style G fill:#00ff44,color:#000
```

### What we cut

```mermaid
graph TD
    subgraph KILLED["Eliminated from hot path"]
        R1["Redis publish<br/>-3ms"]
        R2["Redis subscribe<br/>-5ms"]
        GR["Groq API call<br/>-250ms"]
        BL["Blocking WS await<br/>-5ms"]
        MR["Modal RPC overhead<br/>-100-260ms"]
    end

    subgraph OPTIMIZED["Optimized"]
        PT["PyTorch → ONNX<br/>40ms → 16ms"]
        BA["1-per-market RPC → batched<br/>N calls → ceil(N/50) calls"]
        LC["Cloud → local inference<br/>143ms → 16-69ms"]
    end

    style KILLED fill:#1a0000,stroke:#ff4444
    style OPTIMIZED fill:#001a00,stroke:#00cc44
```

---

## 3. Hot Path — News to Decision (Current)

```mermaid
sequenceDiagram
    participant DB as DBNews
    participant S as Server
    participant T as Tagger
    participant D as Dispatcher
    participant M as Modal (ONNX)
    participant UI as Dashboard

    DB->>S: headline via WebSocket
    S->>T: tag(raw_news)
    T-->>S: TaggedNewsItem (categories, sentiment)

    Note over S: asyncio.create_task()
    S-)UI: broadcast news (fire-and-forget)

    S->>D: _nli_eval_and_broadcast(story)

    Note over D: Filter: enabled_markets ∩ tag overlap
    Note over D: Chunk: matching / 50 = N chunks

    par Parallel RPCs (asyncio.gather)
        D->>M: evaluate_batch(chunk_1)
        D->>M: evaluate_batch(chunk_2)
        D->>M: evaluate_batch(chunk_N)
    end

    M-->>D: [decisions_1]
    M-->>D: [decisions_2]
    M-->>D: [decisions_N]

    loop Each decision
        Note over D: asyncio.create_task()
        D-)UI: broadcast_decision (fire-and-forget)
    end
```

---

## 4. ONNX Inference Pipeline (inside Modal container)

```mermaid
graph LR
    subgraph Input
        H["headlines[]"]
        Q["questions[]"]
    end

    subgraph Tokenizer["AutoTokenizer"]
        TOK["tokenize(premises, hypotheses)<br/>padding=True, max_length=128<br/>return_tensors='np'"]
    end

    subgraph ONNX["ONNX Runtime Session"]
        RUN["session.run(None, {<br/>  input_ids,<br/>  attention_mask<br/>})"]
    end

    subgraph Post["nli_postprocess.py"]
        SM["softmax(logits)"]
        MAP["argmax → YES/NO/SKIP"]
        CONF["confidence × prob_scaling"]
    end

    H --> TOK
    Q --> TOK
    TOK --> RUN
    RUN -->|"logits [N×3]"| SM
    SM --> MAP
    MAP --> CONF
    CONF -->|"[{action, confidence, reasoning}, ...]"| OUT["Decision[]"]
```

---

## 5. Confidence Scaling (Probability-Aware)

```mermaid
graph TD
    RAW["Raw NLI confidence<br/>(softmax probability)"]

    RAW --> YES_CHECK{"action = YES?"}
    RAW --> NO_CHECK{"action = NO?"}
    RAW --> SKIP_CHECK{"action = SKIP?"}

    YES_CHECK -->|"conf × (1 - market_prob)"| YES_OUT["YES confidence<br/><i>Discounted if already priced in</i>"]
    NO_CHECK -->|"conf × market_prob"| NO_OUT["NO confidence<br/><i>Discounted if already priced in</i>"]
    SKIP_CHECK -->|"conf × 0.5"| SKIP_OUT["SKIP confidence<br/><i>Always halved (low signal)</i>"]

    YES_OUT --> CLAMP["clamp(0, 1)"]
    NO_OUT --> CLAMP
    SKIP_OUT --> CLAMP
```

Example: headline says "Fed WILL cut rates" for a market at 95% YES probability.
NLI says YES with 0.9 raw confidence → scaled: `0.9 × (1 - 0.95) = 0.045`. Already priced in — don't trade.

---

## 6. Chunked Parallel Batching (Scaling to 5k+ Markets)

```mermaid
graph TD
    STORY["Incoming story<br/>tags: [macro, fed]"]

    STORY --> FILTER["Tag-filter<br/>12 markets total<br/>4 enabled + matching"]

    FILTER --> CHECK{"N > BATCH_SIZE?"}

    CHECK -->|"N=4, batch=50<br/>1 chunk"| SINGLE["1 Modal RPC<br/>evaluate_batch([4 items])"]

    CHECK -->|"N=5000, batch=50<br/>100 chunks"| MULTI["100 parallel RPCs<br/>asyncio.gather()"]

    SINGLE --> RESULT1["4 decisions<br/>~143ms total"]

    MULTI --> RESULT2["5000 decisions<br/>~143ms total<br/>(same wall-clock!)"]

    style RESULT2 fill:#00aa44,color:#fff
```

The key insight: **wall-clock time is constant regardless of market count**. Modal auto-scales containers. 1 batch or 100 batches in parallel — same latency from the caller's perspective.

---

## 7. Modal Container Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Cold: First RPC / after scaledown
    Cold --> Booting: Container provisioned
    Booting --> Warm: @modal.enter() runs<br/>ONNX model loaded

    Warm --> Processing: evaluate_batch() called
    Processing --> Warm: Return results
    Warm --> Warm: Idle (waiting for next RPC)

    Warm --> ScalingDown: No RPCs for 300s
    ScalingDown --> [*]: Container destroyed

    note right of Cold
        Image: ~300MB
        Boot: ~1.5s (model baked in)
        Avoided by buffer_containers=1
    end note

    note right of Warm
        ONNX session in memory
        Tokenizer cached
        Ready for instant inference
    end note

    note right of Processing
        Tokenize: ~3ms
        ONNX forward: ~30ms
        Postprocess: ~2ms
        Total: ~35ms per batch
    end note
```

---

## 8. Dynamic Market Toggle Flow

```mermaid
sequenceDiagram
    participant U as User (Dashboard)
    participant WS as WebSocket Server
    participant M as main.py
    participant E as enabled_markets set

    Note over U: Clicks toggle on "Fed rates" market

    U->>WS: {type: "toggle_market",<br/>address: "FakeContract3...",<br/>enabled: true}
    WS->>M: _handle_command(data)

    M->>E: enabled_markets.add(address)

    M->>WS: broadcast_json({type: "markets_state", ...})
    WS->>U: Updated markets_state

    Note over U: Market row un-dims, toggle turns green

    Note over M: Next news story...
    Note over M: Tag-filter now includes this market
    Note over M: Modal RPC includes it in batch
```

---

## 9. Data Flow — Types & Serialization

```mermaid
classDiagram
    class RawNewsItem {
        +str id
        +str headline
        +str body
        +str source_handle
        +list urgency_tags
        +list pre_tagged_tickers
        +bool is_priority
    }

    class TaggedNewsItem {
        +RawNewsItem raw
        +float sentiment_score
        +str sentiment_label
        +list categories
        +list tickers
    }

    class StoryPayload {
        +str id
        +str headline
        +str body
        +tuple tags
        +str source
        +datetime timestamp
        +to_dict()
        +from_dict()
    }

    class MarketConfig {
        +str address
        +str question
        +float current_probability
        +tuple tags
        +datetime expires_at
        +to_dict()
        +from_dict()
    }

    class Decision {
        +str action
        +float confidence
        +str reasoning
        +str market_address
        +str story_id
        +float latency_ms
        +str prompt_version
        +to_dict()
    }

    RawNewsItem --> TaggedNewsItem : tagger.tag()
    TaggedNewsItem --> StoryPayload : extract fields
    StoryPayload --> Decision : Modal evaluate_batch()
    MarketConfig --> Decision : provides question + probability
```

---

## 10. Architecture Evolution Timeline

```mermaid
graph LR
    V1["v1 Llama-70B<br/>658ms"] --> V3["v3 Llama-8B<br/>300ms"]
    V3 --> REDIS["Redis + Mock<br/>Full pipeline"]
    REDIS --> DASH["Bloomberg UI<br/>13 panels"]
    DASH --> PT["DeBERTa PyTorch<br/>200ms"]
    PT --> OX["ONNX on Modal<br/>143ms"]
    OX --> DD["Direct dispatch<br/>Batching + toggles"]
    DD --> LO["Local ONNX<br/>16-69ms"]

    style V1 fill:#1a0000,stroke:#ff4444,color:#fff
    style V3 fill:#1a0000,stroke:#ff4444,color:#fff
    style PT fill:#0a0a1a,stroke:#4488ff,color:#fff
    style OX fill:#0a0a1a,stroke:#4488ff,color:#fff
    style DD fill:#001a00,stroke:#00cc44,color:#fff
    style LO fill:#00aa44,color:#fff
```

---

## 11. Deployment Topology

```mermaid
graph TB
    subgraph LOCAL["Dev Machine (Mac)"]
        DEV["Python server<br/>+ Vite dev server"]
    end

    subgraph PROD["Production (planned)"]
        subgraph VPS["VPS — US-East ($5/mo)"]
            SRV["Python server"]
            REDIS["Redis"]
        end

        subgraph MODAL_CLOUD["Modal Cloud"]
            MC1["Container 1<br/>(buffer — always warm)"]
            MC2["Container 2<br/>(auto-scaled)"]
            MC3["Container N<br/>(auto-scaled)"]
        end

        subgraph VERCEL["Vercel (free)"]
            FE["React Dashboard"]
        end
    end

    DEV -->|"~100ms RPC<br/>(residential internet)"| MODAL_CLOUD
    VPS -->|"~30ms RPC<br/>(same AWS region)"| MODAL_CLOUD
    FE <-->|WebSocket| VPS
    SRV --> REDIS

    style DEV fill:#332200,stroke:#ff9800
    style VPS fill:#002200,stroke:#00cc44
    style MODAL_CLOUD fill:#000033,stroke:#4488ff
```

---

## 12. Why Each Optimization Matters

```mermaid
graph LR
    subgraph Before["Before: ~350ms"]
        direction TB
        B1["Groq API<br/>250ms"] ~~~ B2["Redis roundtrip<br/>8ms"]
        B2 ~~~ B3["Blocking WS<br/>5ms"]
        B3 ~~~ B4["Modal RPC<br/>80ms"]
        B4 ~~~ B5["PyTorch<br/>40ms"]
    end

    subgraph After["After: 16–69ms (local ONNX)"]
        direction TB
        A1["ONNX Runtime<br/>10-35ms"] ~~~ A2["Direct dispatch<br/>1ms"]
        A2 ~~~ A3["Fire-and-forget WS<br/>0ms"]
        A3 ~~~ A4["No network<br/>0ms"]
    end

    Before -->|"5–22x faster"| After

    style Before fill:#1a0000,stroke:#ff4444
    style After fill:#001a00,stroke:#00cc44
```

---

## 13. Inference Modes — Local vs Modal vs Modal-Hosted

```mermaid
graph TD
    subgraph LOCAL["--local (current best: 16-69ms)"]
        L1["News → Tagger → ONNX (in-process) → Decision"]
        L2["Zero network. All on your machine."]
    end

    subgraph MODAL_RPC["default (Modal RPC: ~143ms Mac / ~85ms VPS)"]
        M1["News → Tagger → Modal RPC → ONNX (cloud) → Decision"]
        M2["Scales to 5k+ markets via parallel RPCs."]
    end

    subgraph MODAL_HOSTED["future (Modal-hosted: ~40ms est.)"]
        F1["News + Tagger + ONNX all on Modal"]
        F2["Zero RPC. Mac just shows dashboard."]
    end

    style LOCAL fill:#001a00,stroke:#00ff44
    style MODAL_RPC fill:#0a0a1a,stroke:#4488ff
    style MODAL_HOSTED fill:#1a1a00,stroke:#ffcc00
```

| Mode | Command | E2E Latency | Scaling | Cost |
|------|---------|-------------|---------|------|
| **Local ONNX** | `--local` | **16–69ms** | Single machine | $0 |
| Modal RPC | (default) | 85–200ms | 5k+ markets | ~$0.001/story |
| Modal-hosted | (planned) | ~40ms est. | 5k+ markets | ~$0.001/story |
