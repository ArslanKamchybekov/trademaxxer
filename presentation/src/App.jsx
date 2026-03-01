import { useEffect, useRef, useState } from "react"
import Reveal from "reveal.js"
import { motion, AnimatePresence } from "framer-motion"
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, ReferenceLine, ReferenceArea,
  Tooltip,
} from "recharts"

// ── Chart data generators ──

function buildYesData() {
  const pts = []
  for (let t = 0; t <= 300; t += 3) {
    let price
    if (t < 100) {
      price = 82 + Math.sin(t * 0.15) * 2 + (Math.random() - 0.5) * 1.5
    } else {
      const elapsed = t - 100
      const drop = 41 * (1 - Math.exp(-elapsed / 40))
      price = 82 - drop + (Math.random() - 0.5) * 2
    }
    pts.push({ t, price: Math.round(price * 10) / 10 })
  }
  return pts
}

function buildNoData() {
  const pts = []
  for (let t = 0; t <= 300; t += 3) {
    let price
    if (t < 100) {
      price = 18 + Math.sin(t * 0.12) * 1.5 + (Math.random() - 0.5) * 1
    } else {
      const elapsed = t - 100
      const rise = 41 * (1 - Math.exp(-elapsed / 40))
      price = 18 + rise + (Math.random() - 0.5) * 2
    }
    pts.push({ t, price: Math.round(price * 10) / 10 })
  }
  return pts
}

function buildAlphaData() {
  const pts = []
  for (let t = 0; t <= 300; t += 3) {
    const alpha = 100 * Math.exp(-t / 60)
    pts.push({ t, alpha: Math.round(alpha * 10) / 10 })
  }
  return pts
}

const YES_DATA = buildYesData()
const NO_DATA = buildNoData()
const ALPHA_DATA = buildAlphaData()

const HEADLINES = [
  "IDF confirms second wave of strikes on Iranian targets",
  "Pentagon: B-2 bombers deployed from Diego Garcia",
  "Brent crude futures gap up 8% in Asian pre-market",
  "CBOE VIX futures spike to 42 on Iran escalation",
  "CME FedWatch: emergency rate cut probability surges to 68%",
]

// ── Mini chart panel ──

function ChartPanel({ title, value, valueColor, children }) {
  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      padding: "8px 10px", marginBottom: "6px",
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: "4px",
      }}>
        <span style={{
          fontSize: "10px", fontWeight: 700, color: "var(--muted)",
          letterSpacing: "0.1em", textTransform: "uppercase",
        }}>
          {title}
        </span>
        <span style={{ fontSize: "10px", fontWeight: 700, color: valueColor }}>
          {value}
        </span>
      </div>
      <div style={{ height: 100 }}>
        {children}
      </div>
    </div>
  )
}

// ── Animated news ticker ──

function NewsTicker({ active }) {
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    if (!active) return
    const iv = setInterval(() => setIdx(i => (i + 1) % HEADLINES.length), 2500)
    return () => clearInterval(iv)
  }, [active])

  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      padding: "8px 12px", marginTop: "12px", overflow: "hidden", height: "36px",
    }}>
      <AnimatePresence mode="wait">
        <motion.div
          key={idx}
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -20, opacity: 0 }}
          transition={{ duration: 0.3 }}
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
        >
          <span style={{
            fontSize: "8px", fontWeight: 700, color: "var(--no)",
            padding: "1px 4px", border: "1px solid var(--no)",
            letterSpacing: "0.08em", flexShrink: 0,
          }}>
            BREAKING
          </span>
          <span style={{ fontSize: "10px", color: "var(--fg)" }}>
            {HEADLINES[idx]}
          </span>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

// ── Problem slide (animated) ──

function ProblemSlide() {
  const [active, setActive] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => setActive(e.isIntersecting),
      { threshold: 0.5 },
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])

  const chartTooltip = ({ active: a, payload }) => {
    if (!a || !payload?.length) return null
    return (
      <div style={{
        background: "#111", border: "1px solid #1e1e1e",
        padding: "3px 6px", fontSize: "9px", fontFamily: "var(--font)",
      }}>
        <span style={{ color: "#666" }}>t=</span>
        {payload[0]?.payload?.t}
        <span style={{ color: "#666" }}> │ </span>
        {payload[0]?.value}¢
      </div>
    )
  }

  return (
    <section ref={ref}>
      <div className="term-bar">
        <span className="title">PROBLEM</span>
        <span className="meta">LATENCY GAP</span>
      </div>
      <div style={{ display: "flex", gap: "30px" }}>
        <div style={{ width: "420px", flexShrink: 0 }}>
          <span className="section-label">The Problem</span>
          <h2>MARKETS MISPRICE<br />FOR MINUTES</h2>
          <p className="body-text" style={{ marginTop: "8px", fontSize: "0.55em" }}>
            Breaking news hits — prediction markets swing{" "}
            <span className="no">violently</span>. Humans can't
            read, evaluate, and execute <span className="hl">fast enough</span>.
          </p>
          <NewsTicker active={active} />
          {/* Delay bar */}
          <div style={{ marginTop: "16px" }}>
            <div style={{
              height: "6px", background: "var(--card)",
              border: "1px solid var(--border)", position: "relative",
              overflow: "hidden",
            }}>
              <motion.div
                animate={active ? { width: "100%" } : { width: "0%" }}
                transition={{ duration: 4, ease: "linear", repeat: Infinity }}
                style={{
                  height: "100%",
                  background: "linear-gradient(90deg, var(--yes) 0%, var(--primary) 30%, var(--no) 100%)",
                  opacity: 0.6,
                }}
              />
            </div>
            <div style={{
              display: "flex", justifyContent: "space-between",
              fontSize: "8px", marginTop: "3px", color: "var(--muted)",
            }}>
              <span><span className="yes">0s</span> — bot trades</span>
              <span><span className="primary">30s</span> — human reads</span>
              <span><span className="no">2–5 min</span> — manual trade</span>
            </div>
          </div>
          <p style={{ fontSize: "8px", color: "var(--muted)", marginTop: "12px" }}>
            Alpha decays exponentially. By the time a human acts, the edge is gone.
          </p>
        </div>

        {/* Charts */}
        <div style={{ flex: 1 }}>
          <ChartPanel title="Iran Strike — YES" value="82¢ → 41¢" valueColor="var(--yes)">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={YES_DATA} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                <CartesianGrid stroke="#1e1e1e" strokeDasharray="3 3" />
                <XAxis dataKey="t" hide />
                <YAxis domain={[30, 90]} tick={{ fontSize: 8, fill: "#666" }} />
                <Tooltip content={chartTooltip} />
                <ReferenceLine x={100} stroke="#ff9800" strokeDasharray="4 4" strokeWidth={1} />
                <ReferenceArea x1={180} x2={260} fill="rgba(255,152,0,0.06)" />
                <defs>
                  <linearGradient id="yesGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00c853" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00c853" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone" dataKey="price" stroke="#00c853" strokeWidth={1.5}
                  fill="url(#yesGrad)" isAnimationActive={active}
                  animationDuration={3000} animationEasing="ease-out"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Iran Strike — NO" value="18¢ → 59¢" valueColor="var(--no)">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={NO_DATA} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                <CartesianGrid stroke="#1e1e1e" strokeDasharray="3 3" />
                <XAxis dataKey="t" hide />
                <YAxis domain={[10, 70]} tick={{ fontSize: 8, fill: "#666" }} />
                <Tooltip content={chartTooltip} />
                <ReferenceLine x={100} stroke="#ff9800" strokeDasharray="4 4" strokeWidth={1} />
                <ReferenceArea x1={180} x2={260} fill="rgba(255,152,0,0.06)" />
                <defs>
                  <linearGradient id="noGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff1744" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ff1744" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone" dataKey="price" stroke="#ff1744" strokeWidth={1.5}
                  fill="url(#noGrad)" isAnimationActive={active}
                  animationDuration={3000} animationEasing="ease-out"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartPanel>

          <ChartPanel title="Alpha Decay" value="EDGE → 0" valueColor="var(--primary)">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={ALPHA_DATA} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                <CartesianGrid stroke="#1e1e1e" strokeDasharray="3 3" />
                <XAxis dataKey="t" hide />
                <YAxis domain={[0, 100]} tick={{ fontSize: 8, fill: "#666" }} />
                <Tooltip content={chartTooltip} />
                <ReferenceArea x1={0} x2={30} fill="rgba(0,200,83,0.08)" label={{ value: "BOT", fontSize: 7, fill: "#00c853", position: "insideTopLeft" }} />
                <ReferenceArea x1={180} x2={300} fill="rgba(255,23,68,0.05)" label={{ value: "HUMAN", fontSize: 7, fill: "#ff1744", position: "insideTopLeft" }} />
                <Line
                  type="monotone" dataKey="alpha" stroke="#ff9800" strokeWidth={1.5}
                  dot={false} isAnimationActive={active}
                  animationDuration={3000} animationEasing="ease-out"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartPanel>
        </div>
      </div>
    </section>
  )
}

// ── Main App ──

export default function App() {
  const deckRef = useRef(null)
  const deckInstance = useRef(null)

  useEffect(() => {
    if (deckInstance.current) return

    const deck = new Reveal(deckRef.current, {
      hash: true,
      transition: "none",
      backgroundTransition: "none",
      controls: true,
      progress: true,
      center: false,
      width: 1280,
      height: 720,
    })

    deck.initialize().then(() => {
      deckInstance.current = deck
    })

    return () => {
      if (deckInstance.current) {
        deckInstance.current.destroy()
        deckInstance.current = null
      }
    }
  }, [])

  return (
    <div className="reveal" ref={deckRef}>
      <div className="slides">

        {/* ━━ SLIDE 1: TITLE ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">TRADEMAXXER</span>
            <span className="meta">v1.0 &nbsp;│&nbsp; MODAL &middot; GROQ &middot; SOLANA</span>
          </div>
          <div className="title-layout">
            <div className="title-left">
              <div className="team-card">
                <div className="avatar-placeholder" />
                <div className="team-info">
                  <span className="team-name">Anirudh Kuppili</span>
                  <span className="team-role">Eng. @ <span className="primary">Aparavi</span><br />Series A startup</span>
                </div>
              </div>
              <div className="team-card">
                <div className="avatar-placeholder" />
                <div className="team-info">
                  <span className="team-name">Arslan Kamchybekov</span>
                  <span className="team-role">Founding Eng. @ <span className="primary">Kairos</span><br />Backed by Jump Trading &amp; a16z</span>
                </div>
              </div>
              <div className="team-card">
                <div className="avatar-placeholder" />
                <div className="team-info">
                  <span className="team-name">Mathew Randall</span>
                  <span className="team-role">Prev @ <span className="primary">Optiver</span><br />Incoming @ <span className="primary">Etched.ai</span></span>
                </div>
              </div>
            </div>
            <div className="title-right">
              <h1>
                TRADE<span className="primary">MAXXER</span>
              </h1>
              <p className="body-text" style={{ fontSize: "0.5em", marginTop: "12px" }}>
                Autonomous news-to-trade pipeline for prediction markets
              </p>
              <div style={{ marginTop: "24px", display: "flex", gap: "8px" }}>
                <span className="badge badge-modal">Modal</span>
                <span className="badge badge-groq">Groq</span>
                <span className="badge badge-solana">Solana</span>
              </div>
              <div className="stat-row" style={{ marginTop: "32px" }}>
                <div className="stat">
                  <span className="val">&lt;1s</span>
                  <span className="unit">News to Trade</span>
                </div>
                <div className="stat">
                  <span className="val">~250ms</span>
                  <span className="unit">Agent Inference</span>
                </div>
                <div className="stat">
                  <span className="val">20×</span>
                  <span className="unit">Concurrent Evals</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ━━ SLIDE 2: PROBLEM ━━ */}
        <ProblemSlide />

        {/* ━━ SLIDE 3: SOLUTION ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">SOLUTION</span>
            <span className="meta">AUTONOMOUS PIPELINE</span>
          </div>
          <span className="section-label">Our Approach</span>
          <h2>NEWS TO TRADE IN <span className="primary">&lt;1 SECOND</span></h2>
          <p className="body-text" style={{ marginTop: "10px", fontSize: "0.45em" }}>
            TradeMaxxer autonomously ingests live news, reprices markets with an
            LLM agent, and fires trades on Solana — before humans can react.
          </p>
          <div className="features">
            <div className="panel">
              <div className="panel-title">Modal Serverless Fan-Out</div>
              <div className="panel-body">
                Parallel agent evals across all markets as concurrent
                Modal function calls that auto-scale
              </div>
            </div>
            <div className="panel">
              <div className="panel-title">Jupiter Ultra Routing</div>
              <div className="panel-body">
                Trades route through Jupiter Ultra API for optimal
                swap paths across Solana DEX liquidity
              </div>
            </div>
            <div className="panel">
              <div className="panel-title">Groq 32-Token Inference</div>
              <div className="panel-body">
                Responses capped at 32 JSON tokens — action +
                probability — for ~250ms inference
              </div>
            </div>
            <div className="panel">
              <div className="panel-title">Tag-Based Pub/Sub</div>
              <div className="panel-body">
                Redis routes headlines by topic tag so agents
                only evaluate relevant markets
              </div>
            </div>
          </div>
        </section>

        {/* ━━ SLIDE 4: DEMO ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">LIVE DEMO</span>
            <span className="meta">DASHBOARD &middot; REAL-TIME</span>
          </div>
          <span className="section-label">Demo</span>
          <h2>REAL-TIME TRADING DASHBOARD</h2>
          <p style={{ fontSize: "0.38em", color: "var(--muted)", marginTop: "6px" }}>
            <span className="muted">NEWS</span> <span className="pipe">→</span>{" "}
            <span className="muted">AGENT</span> <span className="pipe">→</span>{" "}
            <span className="muted">DECISION</span> <span className="pipe">→</span>{" "}
            <span className="primary">JUPITER SWAP</span> <span className="pipe">→</span>{" "}
            <span className="yes">P&amp;L</span>
          </p>
          <img
            src="/assets/demo-wallet.png"
            alt="TradeMaxxer dashboard"
            className="demo-img"
          />
        </section>

        {/* ━━ SLIDE 5: ARCHITECTURE ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">ARCHITECTURE</span>
            <span className="meta">END-TO-END PIPELINE</span>
          </div>
          <span className="section-label">System Design</span>
          <h2>INGESTION → ROUTING → AGENTS → EXECUTION</h2>
          <img
            src="/assets/architecture.png"
            alt="TradeMaxxer architecture"
            className="arch-img"
          />
        </section>

        {/* ━━ SLIDE 6: PIPELINE TIMING ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">PIPELINE</span>
            <span className="meta">TIMING &middot; 7 STAGES</span>
          </div>
          <span className="section-label">Execution Flow</span>
          <h2>NEWS TO TRADE IN <span className="primary">7 STEPS</span></h2>
          <div className="flow-grid flow-grid-7" style={{ marginTop: "24px" }}>
            <div className="flow-step">
              <span className="num">01</span>
              <span className="label">Ingest</span>
              <span className="desc">WS streams headline</span>
              <span className="time">0ms</span>
            </div>
            <div className="flow-step">
              <span className="num">02</span>
              <span className="label">Tagged</span>
              <span className="desc">VADER + regex</span>
              <span className="time">5ms</span>
            </div>
            <div className="flow-step">
              <span className="num">03</span>
              <span className="label">Routed</span>
              <span className="desc">Redis pub/sub</span>
              <span className="time">6ms</span>
            </div>
            <div className="flow-step">
              <span className="num">04</span>
              <span className="label">Eval</span>
              <span className="desc">Modal + Groq</span>
              <span className="time">350ms</span>
            </div>
            <div className="flow-step">
              <span className="num">05</span>
              <span className="label">Filter</span>
              <span className="desc">6% threshold</span>
              <span className="time">350ms</span>
            </div>
            <div className="flow-step">
              <span className="num">06</span>
              <span className="label">Execute</span>
              <span className="desc">Jupiter Ultra</span>
              <span className="time">355ms</span>
            </div>
            <div className="flow-step">
              <span className="num">07</span>
              <span className="label">Confirm</span>
              <span className="desc">On-chain, P&amp;L</span>
              <span className="time">750ms</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: "24px", marginTop: "24px" }}>
            <div className="panel" style={{ flex: 1 }}>
              <div className="panel-title">Latency Budget</div>
              <div className="kv"><span className="k">Tagger</span><span className="v">~5ms</span></div>
              <div className="kv"><span className="k">Routing</span><span className="v">&lt;1ms</span></div>
              <div className="kv"><span className="k">Groq Inference</span><span className="v primary">~250ms</span></div>
              <div className="kv"><span className="k">Modal RPC</span><span className="v">~50ms</span></div>
              <div className="kv"><span className="k">Executor</span><span className="v">~10ms</span></div>
            </div>
            <div className="panel" style={{ flex: 1 }}>
              <div className="panel-title">Stack</div>
              <div className="kv"><span className="k">LLM</span><span className="v">Llama 3.1 8B</span></div>
              <div className="kv"><span className="k">Inference</span><span className="v yes">Groq</span></div>
              <div className="kv"><span className="k">Compute</span><span className="v primary">Modal</span></div>
              <div className="kv"><span className="k">Chain</span><span className="v" style={{ color: "#b388ff" }}>Solana</span></div>
              <div className="kv"><span className="k">DEX</span><span className="v" style={{ color: "#b388ff" }}>Jupiter Ultra</span></div>
            </div>
          </div>
        </section>

      </div>
    </div>
  )
}
