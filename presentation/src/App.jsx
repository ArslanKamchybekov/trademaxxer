import { createContext, useContext, useEffect, useRef, useState } from "react"
import Reveal from "reveal.js"
import { motion, AnimatePresence } from "framer-motion"
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, ReferenceLine, ReferenceArea,
  Tooltip,
} from "recharts"

const FintechCtx = createContext(true)
function useFin() { return useContext(FintechCtx) }
function T({ fin, simple }) {
  const fintech = useFin()
  return fintech ? fin : simple
}

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
      padding: "10px 12px", marginBottom: "0",
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: "4px",
      }}>
        <span style={{
          fontSize: "12px", fontWeight: 700, color: "var(--muted)",
          letterSpacing: "0.1em", textTransform: "uppercase",
        }}>
          {title}
        </span>
        <span style={{ fontSize: "12px", fontWeight: 700, color: valueColor }}>
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
            fontSize: "11px", fontWeight: 700, color: "var(--no)",
            padding: "2px 6px", border: "1px solid var(--no)",
            letterSpacing: "0.08em", flexShrink: 0,
          }}>
            BREAKING
          </span>
          <span style={{ fontSize: "8px", color: "var(--fg)" }}>
            {HEADLINES[idx]}
          </span>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

// ── Prediction Markets explainer ──

const PM_EXAMPLES = [
  { question: "Will Iran strike Israel by June?", yes: "82¢", no: "18¢", tag: "Geopolitics" },
  { question: "Will the Fed cut rates in March?", yes: "34¢", no: "66¢", tag: "Macro" },
  { question: "Will Bitcoin hit $100k this year?", yes: "57¢", no: "43¢", tag: "Crypto" },
]

function PredictionMarketsSlide({ fintech, setFintech }) {
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

  return (
    <section ref={ref}>
      <div className="term-bar">
        <span className="title">CONTEXT</span>
        <span className="meta">PREDICTION MARKETS 101</span>
      </div>

      <span className="section-label">What is your fintech knowledge?</span>
      <h2 style={{ fontSize: "1.3em" }}>
        TOGGLE OFF FOR SIMPLE EXPLANATION
      </h2>

      {/* Fintech toggle — front and center */}
      <div
        onClick={() => setFintech(f => !f)}
        style={{
          display: "flex", alignItems: "center", gap: "16px",
          marginTop: "20px", cursor: "pointer", userSelect: "none",
        }}
      >
        <div style={{
          fontSize: "14px", fontWeight: 700, letterSpacing: "0.1em",
          color: !fintech ? "var(--primary)" : "var(--muted)",
          transition: "color 0.2s",
        }}>
          SIMPLE
        </div>
        <div style={{
          width: "72px", height: "36px", borderRadius: "18px",
          background: fintech ? "var(--primary)" : "var(--border)",
          position: "relative", transition: "background 0.2s",
          border: "1px solid",
          borderColor: fintech ? "var(--primary)" : "var(--muted)",
          flexShrink: 0,
        }}>
          <motion.div
            animate={{ x: fintech ? 38 : 3 }}
            transition={{ type: "spring", stiffness: 500, damping: 30 }}
            style={{
              width: "30px", height: "30px", borderRadius: "50%",
              background: "#fff", position: "absolute", top: "2px",
            }}
          />
        </div>
        <div style={{
          fontSize: "14px", fontWeight: 700, letterSpacing: "0.1em",
          color: fintech ? "var(--primary)" : "var(--muted)",
          transition: "color 0.2s",
        }}>
          FINTECH
        </div>
        <span style={{
          fontSize: "11px", color: "var(--muted)", marginLeft: "8px",
          fontStyle: "italic",
        }}>
          {fintech ? "Using industry terminology" : "Simplified for everyone"}
        </span>
      </div>

      <p className="body-text" style={{ fontSize: "0.55em", marginTop: "16px", maxWidth: "800px" }}>
        {fintech
          ? <>Prediction markets are financial instruments where contracts pay $1 if an event occurs. Price = implied probability. Trade YES or NO like binary options.</>
          : <>People buy and sell shares on whether something will happen. If you're right, you get $1. The price tells you how likely people think it is.</>
        }
      </p>

      <div style={{
        display: "flex", gap: "24px", marginTop: "28px",
      }}>
        {PM_EXAMPLES.map((ex, i) => (
          <motion.div
            key={ex.question}
            initial={{ opacity: 0, y: 20 }}
            animate={active ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
            transition={{ delay: 0.2 + i * 0.15 }}
            style={{
              flex: 1, background: "var(--card)", border: "1px solid var(--border)",
              padding: "20px",
            }}
          >
            <div style={{
              fontSize: "9px", color: "var(--primary)", letterSpacing: "0.12em",
              textTransform: "uppercase", marginBottom: "6px",
            }}>
              {ex.tag}
            </div>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--fg)", lineHeight: 1.4 }}>
              {ex.question}
            </div>
            <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
              <div style={{
                flex: 1, padding: "8px", textAlign: "center",
                border: "1px solid var(--yes)", background: "rgba(0,200,83,0.06)",
              }}>
                <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--yes)" }}>{ex.yes}</div>
                <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>
                  {fintech ? "YES contract" : "YES, it happens"}
                </div>
              </div>
              <div style={{
                flex: 1, padding: "8px", textAlign: "center",
                border: "1px solid var(--no)", background: "rgba(255,82,82,0.06)",
              }}>
                <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--no)" }}>{ex.no}</div>
                <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>
                  {fintech ? "NO contract" : "NO, it doesn't"}
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={active ? { opacity: 1 } : { opacity: 0 }}
        transition={{ delay: 0.8 }}
        style={{
          display: "flex", gap: "28px", marginTop: "28px",
          justifyContent: "center",
        }}
      >
        <div style={{
          padding: "10px 20px", border: "1px solid var(--border)",
          background: "var(--card)", textAlign: "center",
        }}>
          <div style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.1em" }}>
            {fintech ? "SETTLEMENT" : "PAYOUT"}
          </div>
          <div style={{ fontSize: "15px", color: "var(--fg)", marginTop: "4px" }}>
            {fintech ? "Binary: pays $1 or $0 at expiry" : "Right = $1, Wrong = $0"}
          </div>
        </div>
        <div style={{
          padding: "10px 20px", border: "1px solid var(--border)",
          background: "var(--card)", textAlign: "center",
        }}>
          <div style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.1em" }}>
            {fintech ? "PRICE = PROBABILITY" : "THE PRICE"}
          </div>
          <div style={{ fontSize: "15px", color: "var(--fg)", marginTop: "4px" }}>
            {fintech ? "82¢ = 82% implied probability" : "82¢ means people think 82% chance"}
          </div>
        </div>
        <div style={{
          padding: "10px 20px", border: "1px solid var(--primary)",
          background: "var(--card)", textAlign: "center",
        }}>
          <div style={{ fontSize: "10px", color: "var(--primary)", letterSpacing: "0.1em" }}>
            {fintech ? "THE EDGE" : "THE OPPORTUNITY"}
          </div>
          <div style={{ fontSize: "15px", color: "var(--fg)", marginTop: "4px" }}>
            {fintech ? "Mispricing after news = alpha" : "News moves prices, be fastest"}
          </div>
        </div>
      </motion.div>
    </section>
  )
}

// ── Problem slide (animated) ──

function ProblemSlide() {
  const fin = useFin()
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
        <span className="meta">{fin ? "LATENCY GAP" : "SPEED PROBLEM"}</span>
      </div>
      <div style={{ display: "flex", gap: "48px" }}>
        <div style={{ width: "440px", flexShrink: 0 }}>
          <span className="section-label">The Problem</span>
          <h2>{fin ? <>MARKETS MISPRICE<br />FOR MINUTES</> : <>PRICES ARE WRONG<br />FOR MINUTES</>}</h2>
          <p className="body-text" style={{ marginTop: "16px", fontSize: "0.55em" }}>
            {fin
              ? <>Breaking news hits. Prediction markets swing <span className="no">violently</span>. Humans can't read, evaluate, and execute <span className="hl">fast enough</span>.</>
              : <>Big news breaks. Prices on prediction markets go <span className="no">haywire</span>. People can't react <span className="hl">fast enough</span> to buy or sell.</>
            }
          </p>
          <NewsTicker active={active} />
          {/* Delay bar */}
          <div style={{ marginTop: "24px" }}>
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
              fontSize: "11px", marginTop: "4px", color: "var(--muted)",
            }}>
              <span><span className="yes">0s</span> bot</span>
              <span><span className="primary">30s</span> human reads</span>
              <span><span className="no">2-5 min</span> manual trade</span>
            </div>
          </div>
        </div>

        {/* Charts */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "10px" }}>
          <ChartPanel title="Iran Strike: YES" value="82¢ → 41¢" valueColor="var(--yes)">
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

          <ChartPanel title="Iran Strike: NO" value="18¢ → 59¢" valueColor="var(--no)">
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

          <ChartPanel title={fin ? "Alpha Decay" : "Profit Window Closing"} value={fin ? "EDGE → 0" : "OPPORTUNITY → 0"} valueColor="var(--primary)">
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

// ── Fan-out bar viz for Modal ──

const MODAL_MARKETS = [
  { name: "Iran Strike", ms: 112 },
  { name: "Khamenei", ms: 68 },
  { name: "Brent $130", ms: 187 },
  { name: "Fed Cut", ms: 95 },
  { name: "BTC $150k", ms: 143 },
  { name: "VIX > 40", ms: 210 },
  { name: "Hormuz", ms: 160 },
]

function ModalViz({ active }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "8px" }}>
      {MODAL_MARKETS.map((m, i) => (
        <div key={m.name} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "9px", color: "var(--muted)", width: "72px", textAlign: "right", flexShrink: 0 }}>
            {m.name}
          </span>
          <div style={{ flex: 1, height: "12px", background: "var(--border)", position: "relative", overflow: "hidden" }}>
            <motion.div
              initial={{ width: 0 }}
              animate={active ? { width: `${(m.ms / 250) * 100}%` } : { width: 0 }}
              transition={{ duration: 1.8, delay: 0.12 * i, ease: [0.25, 0.46, 0.45, 0.94] }}
              style={{ height: "100%", background: "var(--primary)", opacity: 0.8 }}
            />
          </div>
          <motion.span
            initial={{ opacity: 0 }}
            animate={active ? { opacity: 1 } : { opacity: 0 }}
            transition={{ delay: 1.4 + 0.12 * i }}
            style={{ fontSize: "9px", color: "var(--primary)", width: "38px", fontVariantNumeric: "tabular-nums" }}
          >
            {m.ms}ms
          </motion.span>
        </div>
      ))}
      <motion.div
        initial={{ opacity: 0 }}
        animate={active ? { opacity: 1 } : { opacity: 0 }}
        transition={{ delay: 2.5 }}
        style={{ fontSize: "9px", color: "var(--yes)", textAlign: "right", marginTop: "3px" }}
      >
        ALL PARALLEL · FASTEST 68ms
      </motion.div>
    </div>
  )
}

// ── Jupiter swap route viz ──

function JupiterViz({ active }) {
  return (
    <div style={{ marginTop: "8px" }}>
      {/* Swap conversion */}
      <div style={{ display: "flex", alignItems: "center", gap: "0" }}>
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={active ? { opacity: 1, x: 0 } : { opacity: 0, x: -10 }}
          transition={{ delay: 0.2 }}
          style={{
            padding: "6px 10px", border: "1px solid var(--border)",
            background: "var(--card)", textAlign: "center",
          }}
        >
          <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--fg)" }}>$0.82</div>
          <div style={{ fontSize: "8px", color: "var(--muted)", letterSpacing: "0.08em" }}>USDC</div>
        </motion.div>
        <motion.span
          initial={{ opacity: 0 }}
          animate={active ? { opacity: 0.5 } : { opacity: 0 }}
          transition={{ delay: 0.5 }}
          style={{ color: "var(--muted)", fontSize: "12px", margin: "0 4px" }}
        >→</motion.span>
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={active ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.8 }}
          transition={{ delay: 0.7, type: "spring", stiffness: 200 }}
          style={{
            padding: "4px 8px", border: "1px solid #b388ff33",
            background: "rgba(179,136,255,0.06)", textAlign: "center",
          }}
        >
          <div style={{ fontSize: "8px", color: "#b388ff", letterSpacing: "0.08em" }}>RAYDIUM</div>
          <div style={{ fontSize: "7px", color: "var(--muted)" }}>SOL-USDC pool</div>
        </motion.div>
        <motion.span
          initial={{ opacity: 0 }}
          animate={active ? { opacity: 0.5 } : { opacity: 0 }}
          transition={{ delay: 1.0 }}
          style={{ color: "var(--muted)", fontSize: "12px", margin: "0 4px" }}
        >→</motion.span>
        <motion.div
          initial={{ opacity: 0, x: 10 }}
          animate={active ? { opacity: 1, x: 0 } : { opacity: 0, x: 10 }}
          transition={{ delay: 1.2 }}
          style={{
            padding: "6px 10px", border: "1px solid rgba(0,200,83,0.3)",
            background: "rgba(0,200,83,0.06)", textAlign: "center",
          }}
        >
          <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--yes)" }}>0.0093</div>
          <div style={{ fontSize: "8px", color: "var(--muted)", letterSpacing: "0.08em" }}>SOL</div>
        </motion.div>
      </div>
      {/* Stats row */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={active ? { opacity: 1 } : { opacity: 0 }}
        transition={{ delay: 1.6 }}
        style={{
          display: "flex", gap: "12px", marginTop: "6px",
          fontSize: "8px", color: "var(--muted)",
        }}
      >
        <span>Impact: <span style={{ color: "var(--yes)" }}>0.01%</span></span>
        <span>Route: <span style={{ color: "#b388ff" }}>Raydium v4</span></span>
        <span>Latency: <span style={{ color: "var(--primary)" }}>85ms</span></span>
      </motion.div>
    </div>
  )
}

// ── Groq latency comparison viz ──

const INFERENCE_BARS = [
  { label: "GPT-4o", ms: 2200, color: "var(--no)" },
  { label: "Claude", ms: 1800, color: "var(--no)" },
  { label: "Llama 70B", ms: 650, color: "var(--primary)" },
  { label: "Groq 8B 32tok", ms: 250, color: "var(--yes)" },
]

function GroqViz({ active }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px", marginTop: "8px" }}>
      {INFERENCE_BARS.map((bar, i) => (
        <div key={bar.label} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "9px", color: "var(--muted)", width: "86px", textAlign: "right", flexShrink: 0 }}>
            {bar.label}
          </span>
          <div style={{ flex: 1, height: "14px", background: "var(--border)", position: "relative", overflow: "hidden" }}>
            <motion.div
              initial={{ width: 0 }}
              animate={active ? { width: `${(bar.ms / 2400) * 100}%` } : { width: 0 }}
              transition={{ duration: 1.6, delay: 0.25 * i, ease: [0.25, 0.46, 0.45, 0.94] }}
              style={{ height: "100%", background: bar.color, opacity: 0.7 }}
            />
          </div>
          <motion.span
            initial={{ opacity: 0 }}
            animate={active ? { opacity: 1 } : { opacity: 0 }}
            transition={{ delay: 1.2 + 0.25 * i }}
            style={{ fontSize: "9px", color: bar.color, width: "42px", fontVariantNumeric: "tabular-nums" }}
          >
            {bar.ms}ms
          </motion.span>
        </div>
      ))}
    </div>
  )
}

// ── Pub/Sub tag routing viz ──

const TAGS = ["#politics", "#crypto", "#financials", "#economics"]
const TAG_COLORS = { "#politics": "var(--no)", "#crypto": "#b388ff", "#financials": "var(--primary)", "#economics": "var(--yes)" }
const ROUTING_EXAMPLE = [
  { headline: "IDF strikes Iran targets", tags: ["#politics", "#financials"] },
  { headline: "Bitcoin spikes 7% on safe-haven", tags: ["#crypto", "#financials"] },
]

function IndexRouteViz({ active }) {
  const [activeHeadline, setActiveHeadline] = useState(0)

  useEffect(() => {
    if (!active) return
    const iv = setInterval(() => setActiveHeadline(i => (i + 1) % ROUTING_EXAMPLE.length), 3000)
    return () => clearInterval(iv)
  }, [active])

  const current = ROUTING_EXAMPLE[activeHeadline]

  return (
    <div style={{ marginTop: "6px" }}>
      <AnimatePresence mode="wait">
        <motion.div
          key={activeHeadline}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
          style={{
            fontSize: "10px", color: "var(--fg)", padding: "4px 8px",
            background: "var(--card)", border: "1px solid var(--border)",
            marginBottom: "6px",
          }}
        >
          "{current.headline}"
        </motion.div>
      </AnimatePresence>
      <div style={{ display: "flex", gap: "5px" }}>
        {TAGS.map(tag => {
          const hit = current.tags.includes(tag)
          return (
            <motion.div
              key={tag}
              animate={{
                borderColor: hit ? TAG_COLORS[tag] : "var(--border)",
                opacity: hit ? 1 : 0.3,
              }}
              transition={{ duration: 0.4 }}
              style={{
                flex: 1, padding: "4px 0", textAlign: "center",
                fontSize: "9px", fontWeight: 700, color: TAG_COLORS[tag],
                border: "1px solid", background: "var(--card)",
                letterSpacing: "0.05em",
              }}
            >
              {tag}
              {hit && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  style={{ fontSize: "7px", color: "var(--yes)", marginTop: "2px" }}
                >
                  ● MATCHED
                </motion.div>
              )}
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ── Solution slide ──

function SolutionSlide() {
  const fin = useFin()
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

  return (
    <section ref={ref}>
      <div className="term-bar">
        <span className="title">SOLUTION</span>
        <span className="meta">AUTONOMOUS PIPELINE</span>
      </div>
      <span className="section-label">Our Approach</span>
      <h2>NEWS TO TRADE IN <span className="primary">&lt;1 SECOND</span></h2>
      <div className="features" style={{ marginTop: "24px" }}>
        <div className="panel">
          <div className="panel-title">{fin ? "Modal Serverless Fan-Out" : "Modal Parallel Processing"}</div>
          <div className="panel-body">
            {fin
              ? "Every headline triggers parallel evals across all markets. Auto-scaling containers."
              : "Every headline checks all markets at once. Servers spin up automatically."
            }
          </div>
          <ModalViz active={active} />
        </div>
        <div className="panel">
          <div className="panel-title">{fin ? "Jupiter Ultra Routing" : "Jupiter Smart Trading"}</div>
          <div className="panel-body">
            {fin
              ? "Trades find optimal swap path across Solana DEX liquidity pools"
              : "Trades find the cheapest path to buy/sell across Solana exchanges"
            }
          </div>
          <JupiterViz active={active} />
        </div>
        <div className="panel">
          <div className="panel-title">{fin ? "Groq 32-Token Inference" : "Groq Instant AI Decisions"}</div>
          <div className="panel-body">
            {fin
              ? "32 JSON tokens. Just action + probability vs traditional LLMs."
              : "AI returns just YES/NO + confidence. Ultra-fast vs typical AI."
            }
          </div>
          <GroqViz active={active} />
        </div>
        <div className="panel">
          <div className="panel-title">{fin ? "In-Memory Pub/Sub" : "Smart News Routing"}</div>
          <div className="panel-body">
            {fin
              ? "Zero-copy in-process bus. Markets subscribe to tag channels. publish() dedupes and fires callbacks via asyncio.gather()."
              : "Headlines are sorted by topic. Each AI only sees news it cares about."
            }
          </div>
          <IndexRouteViz active={active} />
        </div>
      </div>
    </section>
  )
}

// ── Architecture flow ──

function getFlowNodes(fin) {
  return [
    {
      id: "news", label: "WorldMonitor", sub: fin ? "Reuters · AP · Bloomberg" : "Live news feed",
      color: "var(--primary)", tech: "wss://worldmonitor.io · ~2 stories/sec",
      detail: fin
        ? "Persistent WebSocket with exponential backoff reconnect. Normalizes raw JSON → RawNewsItem. Drops non-English."
        : "Always-on connection to a news wire. Receives headlines instantly and filters to English only.",
    },
    {
      id: "tagger", label: "Tagger", sub: fin ? "VADER + regex" : "Categorizer",
      color: "var(--primary)", tech: "~5ms · keyword extraction",
      detail: fin
        ? "Classifies categories (politics, crypto, financials), extracts tickers, determines urgency. Outputs TaggedNewsItem."
        : "Labels each headline by topic (politics, crypto, finance) and how urgent it is. Takes ~5 milliseconds.",
    },
    {
      id: "pubsub", label: fin ? "In-Memory Pub/Sub" : "Topic Router", sub: fin ? "tag → callbacks O(1)" : "Smart routing",
      color: "var(--primary)", tech: "0ms latency · zero-copy · async fan-out",
      detail: fin
        ? "In-process pub/sub bus. Markets subscribe to tag channels on enable, unsubscribe on disable. publish() dedupes and fires all matching callbacks via asyncio.gather()."
        : "An instant message bus. Each market listens for its topics. When news arrives, only the right markets get notified. No network hop, no serialization.",
    },
    {
      id: "modal", label: "Modal Fan-Out", sub: fin ? "Serverless containers" : "Cloud workers",
      color: "#00ff41", tech: "20× concurrency · asyncio.gather()",
      detail: fin
        ? "MarketAgent on Modal. buffer_containers=1 stays warm. All matching markets evaluated in parallel via asyncio.gather()."
        : "Spins up cloud workers to check all relevant markets at the same time. 20 markets checked in parallel.",
    },
    {
      id: "groq", label: "Groq LLM", sub: "Llama 3.1 8B",
      color: "var(--yes)", tech: "32 tokens · JSON mode · 68ms fastest",
      detail: fin
        ? "Returns {action: YES|NO, p: 1-99}. Temp 0.1, timeout 2s. |theo − current| < 6% → SKIP. Confidence = delta × 2."
        : "AI reads the headline and says YES/NO + how confident. Only acts if the price is wrong enough. Fastest: 68ms.",
    },
    {
      id: "decision", label: "Decision", sub: "YES / NO / SKIP",
      color: "var(--primary)", tech: fin ? "theo price + confidence score" : "fair price + confidence",
      detail: fin
        ? "Decision(action, confidence, theo, market_address, latency_ms). Broadcast via WebSocket to all connected clients."
        : "The AI's final call: buy YES, buy NO, or skip. Sent instantly to the dashboard so you see it live.",
    },
    {
      id: "jupiter", label: "Jupiter Ultra", sub: fin ? "Solana DEX routing" : "Trade executor",
      color: "#9945ff", tech: "USDC → SOL · ~85ms quote",
      detail: fin
        ? "Routes through Raydium, Orca pools. Returns outAmount, priceImpact, routePlan for optimal execution path."
        : "Finds the cheapest way to swap dollars for tokens across multiple exchanges. Gets a price quote in ~85ms.",
    },
    {
      id: "solana", label: "Solana TX", sub: fin ? "On-chain confirm" : "Blockchain confirm",
      color: "#9945ff", tech: "~400ms slot · mainnet",
      detail: fin
        ? "Signed transaction submitted for swap. Confirms in one slot. Portfolio mark-to-market updates from agent theo."
        : "The trade is sent to the Solana blockchain and confirmed in ~400ms. Your portfolio updates immediately.",
    },
  ]
}


function FlowNode({ node, selected, onClick, active, delay, size = "normal" }) {
  const isSelected = selected === node.id
  const big = size === "big"
  return (
    <motion.div
      onClick={() => onClick(isSelected ? null : node.id)}
      initial={{ opacity: 0, y: 15 }}
      animate={active ? { opacity: 1, y: 0 } : { opacity: 0, y: 15 }}
      transition={{ delay, type: "spring", stiffness: 200, damping: 20 }}
      whileHover={{ borderColor: node.color, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.97 }}
      style={{
        background: isSelected ? "var(--border)" : "var(--card)",
        border: `1px solid ${isSelected ? node.color : "var(--border)"}`,
        padding: big ? "10px 8px" : "10px 8px",
        cursor: "pointer",
        textAlign: "center",
        width: big ? "130px" : "auto",
        height: big ? "90px" : "auto",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        flexShrink: 0,
      }}
    >
      <div style={{
        fontSize: big ? "14px" : "10px", fontWeight: 700, color: node.color,
        letterSpacing: "0.06em",
      }}>
        {node.label}
      </div>
      <div style={{
        fontSize: big ? "10px" : "7px", color: "var(--muted)",
        marginTop: "4px", lineHeight: 1.3,
      }}>
        {node.sub}
      </div>
    </motion.div>
  )
}

function FlowArrow({ active, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, scaleX: 0 }}
      animate={active ? { opacity: 1, scaleX: 1 } : { opacity: 0, scaleX: 0 }}
      transition={{ delay, duration: 0.3 }}
      style={{
        display: "flex", alignItems: "center", flexShrink: 0,
        transformOrigin: "left",
      }}
    >
      <div style={{
        width: "20px", height: "1px", background: "var(--border)",
      }} />
      <div style={{
        width: 0, height: 0,
        borderTop: "3px solid transparent",
        borderBottom: "3px solid transparent",
        borderLeft: "5px solid var(--border)",
      }} />
    </motion.div>
  )
}

function ArchitectureSlide({ onModalReveal, onSolanaReveal }) {
  const fin = useFin()
  const [selected, setSelected] = useState(null)
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

  const flowNodes = getFlowNodes(fin)
  const allNodes = flowNodes
  const selectedNode = allNodes.find(n => n.id === selected)

  return (
    <section ref={ref} style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="term-bar">
        <span className="title">ARCHITECTURE</span>
        <span className="meta">CLICK ANY NODE</span>
      </div>
      <span className="section-label">System Design</span>
      <h2 style={{ fontSize: "1.2em" }}>{fin ? "NEWS → TAG → PUB/SUB → EVAL → DECIDE → TRADE" : "How it works under the hood"}</h2>

      {/* Main flow with fan-out */}
      <div style={{
        display: "flex", alignItems: "center",
        marginTop: "32px", gap: "0",
      }}>
        {/* Phase 1: WorldMonitor → Tagger */}
        {flowNodes.slice(0, 2).map((node, i) => (
          <div key={node.id} style={{ display: "flex", alignItems: "center" }}>
            <FlowNode
              node={node} selected={selected} onClick={setSelected}
              active={active} delay={0.1 * i} size="big"
            />
            <FlowArrow active={active} delay={0.1 * i + 0.05} />
          </div>
        ))}

        {/* Phase 2: Inverted Index lookup table → Modal Fan-Out */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={active ? { opacity: 1 } : { opacity: 0 }}
          transition={{ delay: 0.2 }}
          style={{ display: "flex", alignItems: "center", flexShrink: 0 }}
        >
          {/* Inverted index table */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={active ? { opacity: 1, scale: 1 } : {}}
            transition={{ delay: 0.25 }}
            onClick={() => setSelected(selected === "pubsub" ? null : "pubsub")}
            style={{
              display: "flex", flexDirection: "column",
              border: `1px solid ${selected === "pubsub" ? "var(--primary)" : "var(--border)"}`,
              background: selected === "pubsub" ? "var(--border)" : "var(--card)",
              cursor: "pointer", overflow: "hidden",
              width: "150px",
            }}
          >
            <div style={{
              padding: "5px 10px",
              borderBottom: "1px solid var(--border)",
              fontSize: "10px", fontWeight: 700, color: "var(--primary)",
              letterSpacing: "0.06em", textAlign: "center",
            }}>
              {fin ? "In-Mem Pub/Sub" : "Topic Router"}
            </div>
            {[
              { tag: "politics", subs: 3 },
              { tag: "crypto", subs: 2 },
              { tag: "financials", subs: 4 },
            ].map((row, i) => (
              <motion.div
                key={row.tag}
                initial={{ opacity: 0, x: -10 }}
                animate={active ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: 0.3 + i * 0.08 }}
                style={{
                  borderBottom: i < 2 ? "1px solid var(--border)" : "none",
                  padding: "3px 10px",
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                }}
              >
                <span style={{ fontSize: "8px", color: "var(--primary)", fontWeight: 600, letterSpacing: "0.04em" }}>
                  {row.tag}
                </span>
                <span style={{ fontSize: "7px", color: "var(--muted)" }}>
                  {row.subs} subs
                </span>
              </motion.div>
            ))}
          </motion.div>

          <FlowArrow active={active} delay={0.5} />

          {/* Modal container box — 4 rows */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={active ? { opacity: 1, scale: 1 } : {}}
            transition={{ delay: 0.55 }}
            onClick={() => setSelected(selected === "modal" ? null : "modal")}
            style={{
              display: "flex", flexDirection: "column",
              border: `1px solid ${selected === "modal" ? "#00ff41" : "var(--border)"}`,
              background: selected === "modal" ? "var(--border)" : "var(--card)",
              cursor: "pointer", overflow: "hidden",
              width: "130px",
            }}
          >
            <div style={{
              padding: "5px 10px",
              borderBottom: "1px solid var(--border)",
              fontSize: "10px", fontWeight: 700, color: "#00ff41",
              letterSpacing: "0.06em", textAlign: "center",
            }}>
              Modal Fan-Out
            </div>
            {[1, 2, 3, 4].map(n => (
              <motion.div
                key={n}
                initial={{ width: "0%" }}
                animate={active ? { width: "100%" } : { width: "0%" }}
                transition={{ delay: 0.6 + n * 0.08, duration: 0.4 }}
                style={{
                  borderBottom: n < 4 ? "1px solid var(--border)" : "none",
                  padding: "3px 10px",
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                }}
              >
                <span style={{ fontSize: "7px", color: "var(--muted)" }}>container-{n}</span>
                <motion.div
                  initial={{ width: 0 }}
                  animate={active ? { width: "40px" } : { width: 0 }}
                  transition={{ delay: 0.8 + n * 0.1, duration: 0.3 }}
                  style={{ height: "3px", background: "#00ff41", opacity: 0.5 }}
                />
              </motion.div>
            ))}
          </motion.div>
        </motion.div>

        <FlowArrow active={active} delay={0.7} />

        {/* Phase 3: Groq → Decision → Jupiter → Solana */}
        {flowNodes.slice(4).map((node, i) => (
          <div key={node.id} style={{ display: "flex", alignItems: "center" }}>
            <FlowNode
              node={node} selected={selected} onClick={setSelected}
              active={active} delay={0.8 + 0.1 * i} size="big"
            />
            {i < flowNodes.slice(4).length - 1 && (
              <FlowArrow active={active} delay={0.85 + 0.1 * i} />
            )}
          </div>
        ))}
      </div>

      {/* Detail panel */}
      <div style={{ marginTop: "40px", minHeight: "90px" }}>
        <AnimatePresence mode="wait">
          {selectedNode ? (
            <motion.div
              key={selectedNode.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              style={{
                background: "var(--card)", border: `1px solid ${selectedNode.color}`,
                padding: "16px 20px", display: "flex", gap: "30px",
                width: "100%", boxSizing: "border-box",
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: "16px", fontWeight: 700, color: selectedNode.color,
                  letterSpacing: "0.06em",
                }}>
                  {selectedNode.label}
                  <span style={{ fontSize: "11px", color: "var(--muted)", marginLeft: "8px", fontWeight: 400 }}>
                    {selectedNode.sub}
                  </span>
                </div>
                <div style={{
                  fontSize: "13px", color: "var(--fg)", marginTop: "8px", lineHeight: 1.6,
                }}>
                  {selectedNode.detail}
                </div>
              </div>
              <div style={{
                width: "200px", flexShrink: 0, borderLeft: "1px solid var(--border)",
                paddingLeft: "16px", display: "flex", flexDirection: "column", justifyContent: "center",
              }}>
                <div style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
                  TECH
                </div>
                <div style={{ fontSize: "13px", color: selectedNode.color, marginTop: "4px", lineHeight: 1.5 }}>
                  {selectedNode.tech}
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.6 }}
              style={{
                fontSize: "10px", color: "var(--muted)", textAlign: "center",
                padding: "20px 0",
              }}
            >
              CLICK ANY NODE TO INSPECT · 10 COMPONENTS · NEWS → TRADE IN &lt;1s
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Secret slide CTAs */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "50px" }}>
        {/* Solana CTA */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={active ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
          transition={{ delay: 1.2, type: "spring", stiffness: 200 }}
          whileHover={{ scale: 1.03, boxShadow: "0 0 24px rgba(153,69,255,0.25)" }}
          whileTap={{ scale: 0.97 }}
          onClick={onSolanaReveal}
          style={{
            display: "flex", alignItems: "center", gap: "14px",
            padding: "14px 24px",
            background: "rgba(153,69,255,0.06)",
            border: "1px solid #9945ff",
            cursor: "pointer",
          }}
        >
          <svg width="28" height="28" viewBox="0 0 100 100" fill="none">
            <defs>
              <linearGradient id="solGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#9945ff" />
                <stop offset="100%" stopColor="#14f195" />
              </linearGradient>
            </defs>
            <polygon points="10,72 80,72 90,82 20,82" fill="url(#solGrad1)" />
            <polygon points="10,46 80,46 90,56 20,56" fill="url(#solGrad1)" />
            <polygon points="20,20 90,20 80,30 10,30" fill="url(#solGrad1)" />
          </svg>
          <div>
            <div style={{
              fontSize: "16px", fontWeight: 700, color: "#9945ff",
              letterSpacing: "0.04em",
            }}>
              Are you the Solana team?
            </div>
            <div style={{ fontSize: "10px", color: "#555", marginTop: "2px", letterSpacing: "0.08em" }}>
              CLICK FOR JUPITER ULTRA + ON-CHAIN EXECUTION →
            </div>
          </div>
        </motion.div>

        {/* Modal CTA */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={active ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
          transition={{ delay: 1.4, type: "spring", stiffness: 200 }}
          whileHover={{ scale: 1.03, boxShadow: "0 0 24px rgba(0,255,65,0.25)" }}
          whileTap={{ scale: 0.97 }}
          onClick={onModalReveal}
          style={{
            display: "flex", alignItems: "center", gap: "14px",
            padding: "14px 24px",
            background: "rgba(0,255,65,0.06)",
            border: "1px solid #00ff41",
            cursor: "pointer",
          }}
        >
          <span style={{
            fontSize: "18px", fontWeight: 700, color: "#00ff41",
            letterSpacing: "0.06em",
          }}>
            ◆◆
          </span>
          <div>
            <div style={{
              fontSize: "16px", fontWeight: 700, color: "#00ff41",
              letterSpacing: "0.04em",
            }}>
              Are you the Modal team?
            </div>
            <div style={{ fontSize: "10px", color: "#555", marginTop: "2px", letterSpacing: "0.08em" }}>
              CLICK FOR A DEEP DIVE INTO OUR MODAL ARCHITECTURE →
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}

// ── Secret Modal deep-dive slide ──

const MODAL_GREEN = "#00ff41"
const MODAL_BG = "#0b0b0b"

const MODAL_FEATURES = [
  {
    title: "MarketAgent Deployment",
    code: `app = modal.App("trademaxxer-agents")
@app.cls(
  concurrency_limit=20,
  scaledown_window=300,
  buffer_containers=1,
)
class MarketAgent:
    @modal.enter()
    def init(self):
        self.groq = GroqClient()`,
    detail: "One class, 20 concurrent evaluations per container. Buffer container stays warm. 300s scaledown window means zero cold starts during trading.",
  },
  {
    title: "Parallel Fan-Out",
    code: `# 20 markets, 1 wall-clock cycle
results = await asyncio.gather(*[
    agent.evaluate.remote.aio(
        story.to_dict(),
        market.to_dict()
    )
    for market in matching_markets
])`,
    detail: "Every headline triggers parallel evals across all matching markets. Modal auto-scales containers. 20 markets = same latency as 1.",
  },
  {
    title: "Zero Cold Starts",
    code: `buffer_containers = 1  # always warm
scaledown_window = 300  # 5 min grace

# Warmup on boot
async def _warmup_modal():
    agent = modal.Cls.from_name(
        "trademaxxer-agents",
        "MarketAgent"
    )()
    await agent.evaluate.remote.aio(...)`,
    detail: "Pre-warmed container + startup warmup ping. First real headline hits a hot container. No 3-second cold start penalty.",
  },
]

function ModalDeepDive() {
  const [active, setActive] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const ref = useRef(null)

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => setActive(e.isIntersecting),
      { threshold: 0.3 },
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])

  const feat = MODAL_FEATURES[selectedIdx]

  return (
    <section
      ref={ref}
      style={{
        background: MODAL_BG,
        padding: "40px 60px",
      }}
    >
      {/* Modal header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: `1px solid ${MODAL_GREEN}22`,
        paddingBottom: "10px", marginBottom: "28px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            fontSize: "22px", fontWeight: 800, color: MODAL_GREEN,
            letterSpacing: "0.02em",
          }}>
            ◆◆ Modal
          </div>
          <span style={{
            fontSize: "10px", color: "#333", letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}>
            SECRET SLIDE
          </span>
        </div>
        <span style={{
          fontSize: "10px", padding: "3px 10px",
          border: `1px solid ${MODAL_GREEN}`,
          color: MODAL_GREEN, letterSpacing: "0.08em",
        }}>
          DEEP DIVE
        </span>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={active ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.4 }}
      >
        <div style={{
          fontSize: "11px", color: MODAL_GREEN, letterSpacing: "0.2em",
          textTransform: "uppercase", marginBottom: "8px",
        }}>
          How TradeMaxxer Uses Modal
        </div>
        <h2 style={{
          fontSize: "1.6em", color: "#fff", letterSpacing: "0.04em",
        }}>
          SERVERLESS <span style={{ color: MODAL_GREEN }}>AGENT INFRASTRUCTURE</span>
        </h2>
      </motion.div>

      <div style={{ display: "flex", gap: "32px", marginTop: "28px" }}>
        {/* Left: feature selector */}
        <div style={{ width: "280px", flexShrink: 0, display: "flex", flexDirection: "column", gap: "10px" }}>
          {MODAL_FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, x: -20 }}
              animate={active ? { opacity: 1, x: 0 } : {}}
              transition={{ delay: 0.2 + i * 0.1 }}
              onClick={() => setSelectedIdx(i)}
              style={{
                padding: "14px 16px",
                background: selectedIdx === i ? `${MODAL_GREEN}12` : "transparent",
                border: `1px solid ${selectedIdx === i ? MODAL_GREEN : "#1a1a1a"}`,
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              <div style={{
                fontSize: "12px", fontWeight: 700,
                color: selectedIdx === i ? MODAL_GREEN : "#888",
                letterSpacing: "0.06em",
              }}>
                {String(i + 1).padStart(2, "0")}. {f.title}
              </div>
            </motion.div>
          ))}

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={active ? { opacity: 1 } : {}}
            transition={{ delay: 0.8 }}
            style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}
          >
            {[
              { label: "Containers", val: "Auto-scaling" },
              { label: "Concurrency", val: "20x per container" },
              { label: "Cold Start", val: "Eliminated" },
              { label: "Cost", val: "~$0.001/story" },
            ].map(s => (
              <div key={s.label} style={{
                display: "flex", justifyContent: "space-between",
                fontSize: "10px", padding: "4px 0",
                borderBottom: "1px solid #1a1a1a",
              }}>
                <span style={{ color: "#555" }}>{s.label}</span>
                <span style={{ color: MODAL_GREEN }}>{s.val}</span>
              </div>
            ))}
          </motion.div>
        </div>

        {/* Right: code + detail */}
        <div style={{ flex: 1 }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={selectedIdx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {/* Code block */}
              <div style={{
                background: "#0d0d0d",
                border: `1px solid ${MODAL_GREEN}33`,
                padding: "20px",
                fontFamily: "var(--font)",
                fontSize: "12px",
                lineHeight: 1.7,
                color: "#ccc",
                whiteSpace: "pre",
                overflow: "auto",
              }}>
                {feat.code.split("\n").map((line, i) => (
                  <div key={i}>
                    <span style={{ color: "#333", marginRight: "16px", userSelect: "none" }}>
                      {String(i + 1).padStart(2, " ")}
                    </span>
                    {line.split(/(modal\.\w+|asyncio\.gather|buffer_containers|scaledown_window|concurrency_limit|\.remote\.aio|@app\.cls|@modal\.enter|MarketAgent|GroqClient)/).map((part, j) =>
                      /^(modal\.\w+|asyncio\.gather|buffer_containers|scaledown_window|concurrency_limit|\.remote\.aio|@app\.cls|@modal\.enter|MarketAgent|GroqClient)$/.test(part)
                        ? <span key={j} style={{ color: MODAL_GREEN }}>{part}</span>
                        : <span key={j}>{part}</span>
                    )}
                  </div>
                ))}
              </div>

              {/* Description */}
              <div style={{
                marginTop: "16px",
                padding: "14px 18px",
                border: "1px solid #1a1a1a",
                fontSize: "13px",
                color: "#aaa",
                lineHeight: 1.7,
              }}>
                {feat.detail}
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Bottom bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={active ? { opacity: 1 } : {}}
            transition={{ delay: 1.0 }}
            style={{
              marginTop: "16px",
              display: "flex", gap: "24px", justifyContent: "center",
            }}
          >
            {[
              { val: "20×", label: "CONCURRENT EVALS" },
              { val: "0ms", label: "COLD START" },
              { val: "<$0.01", label: "PER 100 STORIES" },
              { val: "300s", label: "WARM WINDOW" },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={active ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 1.2 + i * 0.1 }}
                style={{ textAlign: "center" }}
              >
                <div style={{
                  fontSize: "22px", fontWeight: 700, color: MODAL_GREEN,
                  fontFamily: "var(--font)",
                }}>
                  {s.val}
                </div>
                <div style={{
                  fontSize: "8px", color: "#555", letterSpacing: "0.12em",
                  marginTop: "3px",
                }}>
                  {s.label}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}

// ── Secret Solana deep-dive slide ──

const SOL_PURPLE = "#9945ff"
const SOL_GREEN = "#14f195"
const SOL_BG = "#0b0b0b"

const SOLANA_FEATURES = [
  {
    title: "Jupiter Ultra Routing",
    code: `// Quote: find optimal swap path
const quote = await fetch(
  "https://lite-api.jup.ag/ultra/v1/order", {
    method: "POST",
    body: JSON.stringify({
      inputMint: USDC_MINT,
      outputMint: SOL_MINT,
      amount: usdcAmount * 1e6,
    })
  }
)
// Routes: Raydium, Orca, Meteora
// Returns: outAmount, priceImpact`,
    detail: "Jupiter Ultra aggregates liquidity across all Solana DEXs. One API call finds the best swap path. We route USDC to SOL for every trade decision the agent makes.",
  },
  {
    title: "Real-Time Mark-to-Market",
    code: `// On every agent decision:
const theo = decision.theo  // 0.91
const current = market.probability  // 0.82
const delta = Math.abs(theo - current)

if (delta > SKIP_THRESHOLD) {
  // Execute trade via Jupiter
  await executeSwap(direction, amount)
}

// Mark ALL positions to theo price
positions.forEach(p => {
  p.currentValue = p.contracts * theo
})`,
    detail: "Every agent decision updates portfolio mark-to-market using the theoretical fair price. Positions are valued in real-time, not at stale market prices. P&L reflects the agent's edge.",
  },
  {
    title: "On-Chain Confirmation",
    code: `// Solana TX lifecycle
t=0ms    Decision: YES @ 91% (current 82%)
t=85ms   Jupiter quote received
t=90ms   Transaction constructed + signed
t=400ms  Slot confirmed on mainnet
t=401ms  Portfolio updated

// ~400ms slot time on Solana mainnet
// Sub-second from decision to confirm`,
    detail: "Solana's ~400ms slot time means trades confirm almost instantly. Combined with Jupiter Ultra's ~85ms quote time, we go from agent decision to on-chain confirmation in under 500ms.",
  },
]

function SolanaDeepDive() {
  const [active, setActive] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const ref = useRef(null)

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => setActive(e.isIntersecting),
      { threshold: 0.3 },
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])

  const feat = SOLANA_FEATURES[selectedIdx]

  return (
    <section
      ref={ref}
      style={{
        background: SOL_BG,
        padding: "40px 60px",
      }}
    >
      {/* Solana header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: `1px solid ${SOL_PURPLE}22`,
        paddingBottom: "10px", marginBottom: "28px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            display: "flex", alignItems: "center", gap: "10px",
          }}>
            <svg width="26" height="26" viewBox="0 0 100 100" fill="none">
              <defs>
                <linearGradient id="solGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#9945ff" />
                  <stop offset="100%" stopColor="#14f195" />
                </linearGradient>
              </defs>
              <polygon points="10,72 80,72 90,82 20,82" fill="url(#solGrad2)" />
              <polygon points="10,46 80,46 90,56 20,56" fill="url(#solGrad2)" />
              <polygon points="20,20 90,20 80,30 10,30" fill="url(#solGrad2)" />
            </svg>
            <span style={{ fontSize: "22px", fontWeight: 800, color: SOL_PURPLE, letterSpacing: "0.02em" }}>Solana</span>
          </div>
          <span style={{
            fontSize: "10px", color: "#333", letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}>
            SECRET SLIDE
          </span>
        </div>
        <span style={{
          fontSize: "10px", padding: "3px 10px",
          border: `1px solid ${SOL_PURPLE}`,
          color: SOL_PURPLE, letterSpacing: "0.08em",
        }}>
          DEEP DIVE
        </span>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={active ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.4 }}
      >
        <div style={{
          fontSize: "11px", color: SOL_PURPLE, letterSpacing: "0.2em",
          textTransform: "uppercase", marginBottom: "8px",
        }}>
          How TradeMaxxer Uses Solana
        </div>
        <h2 style={{
          fontSize: "1.6em", color: "#fff", letterSpacing: "0.04em",
        }}>
          JUPITER ULTRA + <span style={{ color: SOL_GREEN }}>ON-CHAIN EXECUTION</span>
        </h2>
      </motion.div>

      <div style={{ display: "flex", gap: "32px", marginTop: "28px" }}>
        {/* Left: feature selector */}
        <div style={{ width: "280px", flexShrink: 0, display: "flex", flexDirection: "column", gap: "10px" }}>
          {SOLANA_FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, x: -20 }}
              animate={active ? { opacity: 1, x: 0 } : {}}
              transition={{ delay: 0.2 + i * 0.1 }}
              onClick={() => setSelectedIdx(i)}
              style={{
                padding: "14px 16px",
                background: selectedIdx === i ? `${SOL_PURPLE}12` : "transparent",
                border: `1px solid ${selectedIdx === i ? SOL_PURPLE : "#1a1a1a"}`,
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              <div style={{
                fontSize: "12px", fontWeight: 700,
                color: selectedIdx === i ? SOL_PURPLE : "#888",
                letterSpacing: "0.06em",
              }}>
                {String(i + 1).padStart(2, "0")}. {f.title}
              </div>
            </motion.div>
          ))}

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={active ? { opacity: 1 } : {}}
            transition={{ delay: 0.8 }}
            style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}
          >
            {[
              { label: "Chain", val: "Solana Mainnet" },
              { label: "DEX Aggregator", val: "Jupiter Ultra" },
              { label: "Swap Pair", val: "USDC ↔ SOL" },
              { label: "Quote Latency", val: "~85ms" },
              { label: "Slot Confirm", val: "~400ms" },
            ].map(s => (
              <div key={s.label} style={{
                display: "flex", justifyContent: "space-between",
                fontSize: "10px", padding: "4px 0",
                borderBottom: "1px solid #1a1a1a",
              }}>
                <span style={{ color: "#555" }}>{s.label}</span>
                <span style={{ color: SOL_GREEN }}>{s.val}</span>
              </div>
            ))}
          </motion.div>
        </div>

        {/* Right: code + detail */}
        <div style={{ flex: 1 }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={selectedIdx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {/* Code block */}
              <div style={{
                background: "#0d0d0d",
                border: `1px solid ${SOL_PURPLE}33`,
                padding: "20px",
                fontFamily: "var(--font)",
                fontSize: "12px",
                lineHeight: 1.7,
                color: "#ccc",
                whiteSpace: "pre",
                overflow: "auto",
              }}>
                {feat.code.split("\n").map((line, i) => (
                  <div key={i}>
                    <span style={{ color: "#333", marginRight: "16px", userSelect: "none" }}>
                      {String(i + 1).padStart(2, " ")}
                    </span>
                    {line.split(/(Jupiter|USDC|SOL|Solana|Raydium|Orca|Meteora|mainnet|theo|decision\.theo|SKIP_THRESHOLD|executeSwap|priceImpact|outAmount|jup\.ag)/).map((part, j) =>
                      /^(Jupiter|USDC|SOL|Solana|Raydium|Orca|Meteora|mainnet|theo|decision\.theo|SKIP_THRESHOLD|executeSwap|priceImpact|outAmount|jup\.ag)$/.test(part)
                        ? <span key={j} style={{ color: SOL_PURPLE }}>{part}</span>
                        : /^(\/\/.*)$/.test(part)
                          ? <span key={j} style={{ color: "#555" }}>{part}</span>
                          : <span key={j}>{part}</span>
                    )}
                  </div>
                ))}
              </div>

              {/* Description */}
              <div style={{
                marginTop: "16px",
                padding: "14px 18px",
                border: "1px solid #1a1a1a",
                fontSize: "13px",
                color: "#aaa",
                lineHeight: 1.7,
              }}>
                {feat.detail}
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Bottom bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={active ? { opacity: 1 } : {}}
            transition={{ delay: 1.0 }}
            style={{
              marginTop: "16px",
              display: "flex", gap: "24px", justifyContent: "center",
            }}
          >
            {[
              { val: "~85ms", label: "JUPITER QUOTE" },
              { val: "~400ms", label: "SLOT CONFIRM" },
              { val: "<500ms", label: "DECISION → CHAIN" },
              { val: "USDC↔SOL", label: "SWAP PAIR" },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 10 }}
                animate={active ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 1.2 + i * 0.1 }}
                style={{ textAlign: "center" }}
              >
                <div style={{
                  fontSize: "22px", fontWeight: 700, color: SOL_GREEN,
                  fontFamily: "var(--font)",
                }}>
                  {s.val}
                </div>
                <div style={{
                  fontSize: "8px", color: "#555", letterSpacing: "0.12em",
                  marginTop: "3px",
                }}>
                  {s.label}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}

// ── Closing slide ──

const CLOSING_STATS = [
  { val: "<1s", label: "News → Trade" },
  { val: "68ms", label: "Fastest Decision" },
  { val: "20×", label: "Parallel Evals" },
  { val: "32", label: "LLM Tokens" },
]

function ClosingSlide() {
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

  return (
    <section ref={ref}>
      <div className="term-bar">
        <span className="title">EOF</span>
        <span className="meta">SESSION COMPLETE</span>
      </div>

      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", height: "85%", gap: "20px",
      }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={active ? { opacity: 1, scale: 1 } : {}}
          transition={{ duration: 0.5, type: "spring", stiffness: 120 }}
          style={{ textAlign: "center" }}
        >
          <div style={{
            fontSize: "56px", fontWeight: 800, letterSpacing: "-0.02em",
            lineHeight: 1,
          }}>
            TRADE<span className="primary">MAXXER</span>
          </div>
          <div style={{
            fontSize: "14px", color: "var(--muted)", marginTop: "12px",
            letterSpacing: "0.2em", textTransform: "uppercase",
          }}>
            Autonomous Prediction Market Trading
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={active ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.3, duration: 0.4 }}
          style={{
            display: "flex", gap: "32px", marginTop: "8px",
          }}
        >
          {CLOSING_STATS.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 15 }}
              animate={active ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.5 + i * 0.1 }}
              style={{
                textAlign: "center",
                padding: "12px 20px",
                background: "var(--card)",
                border: "1px solid var(--border)",
                minWidth: "100px",
              }}
            >
              <div style={{
                fontSize: "28px", fontWeight: 700, color: "var(--primary)",
                fontFamily: "var(--font-mono)",
              }}>
                {s.val}
              </div>
              <div style={{
                fontSize: "10px", color: "var(--muted)", marginTop: "4px",
                letterSpacing: "0.1em", textTransform: "uppercase",
              }}>
                {s.label}
              </div>
            </motion.div>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={active ? { opacity: 1 } : {}}
          transition={{ delay: 1.0, duration: 0.6 }}
          style={{
            marginTop: "24px",
            padding: "16px 48px",
            border: "2px solid var(--primary)",
            textAlign: "center",
          }}
        >
          <div style={{
            fontSize: "28px", fontWeight: 700, color: "var(--primary)",
            letterSpacing: "0.15em",
          }}>
            QUESTIONS?
          </div>
          <div style={{
            fontSize: "12px", color: "var(--muted)", marginTop: "6px",
            letterSpacing: "0.08em",
          }}>
            Anirudh &middot; Arslan &middot; Mathew
          </div>
        </motion.div>
      </div>
    </section>
  )
}

// ── Main App ──

export default function App() {
  const deckRef = useRef(null)
  const deckInstance = useRef(null)
  const [fintech, setFintech] = useState(true)
  const [modalRevealed, setModalRevealed] = useState(false)
  const [solanaRevealed, setSolanaRevealed] = useState(false)

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
    <FintechCtx.Provider value={fintech}>
    <div className="reveal" ref={deckRef}>
      <div className="slides">

        {/* ━━ SLIDE 1: TITLE ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">The Future Of Prediction Markets</span>
          </div>
          <div style={{
            display: "flex", gap: "48px", marginTop: "20px",
            alignItems: "center", height: "85%",
          }}>
            {/* Left — title & info */}
            <div style={{ flex: 1 }}>
              <h1 style={{ fontSize: "3.2em", lineHeight: 1 }}>
                TRADE<span className="primary">MAXXER</span>
              </h1>
              <p className="body-text" style={{ fontSize: "0.7em", marginTop: "14px" }}>
                Autonomous news-to-trade pipeline for prediction markets
              </p>
              <div style={{ marginTop: "24px", display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "11px", color: "var(--muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Powered by</span>
                <span className="badge badge-modal">Modal</span>
                <span className="badge badge-solana">Solana</span>
              </div>
              <div className="stat-row" style={{ marginTop: "36px" }}>
                <div className="stat">
                  <span className="val">&lt;1s</span>
                  <span className="unit">News to Trade</span>
                </div>
                <div className="stat">
                  <span className="val">68ms</span>
                  <span className="unit">Fastest Decision</span>
                </div>
                <div className="stat">
                  <span className="val">20×</span>
                  <span className="unit">Concurrent Evals</span>
                </div>
              </div>
            </div>

            {/* Right — team photos */}
            <div style={{
              display: "flex", flexDirection: "column", gap: "14px",
              width: "480px", flexShrink: 0,
            }}>
              {[
                { img: "/assets/team/arslan.JPG", name: "Arslan Kamchybekov", role: <>Founding Eng. @ <span className="primary">Kairos</span><br />Backed by <span className="primary">Geneva Trading</span> &amp; <span className="primary">a16z</span></> },
                { img: "/assets/team/ani.JPG", name: "Anirudh Kuppili", role: <>Eng. @ <span className="primary">Aparavi</span><br /><span className="primary">Series A</span> startup</> },
                { img: "/assets/team/matt.JPG", name: "Mathew Randal", role: <>Eng. @ <span className="primary">Optiver</span><br />Quant @ Illinois</> },
              ].map((m) => (
                <div key={m.name} style={{
                  display: "flex", alignItems: "center", gap: "16px",
                  background: "var(--card)", border: "1px solid var(--border)",
                  padding: "14px 18px",
                }}>
                  <img
                    src={m.img}
                    alt={m.name}
                    style={{
                      width: "72px", height: "72px", objectFit: "cover",
                      border: "2px solid var(--border)", flexShrink: 0,
                    }}
                  />
                  <div>
                    <div style={{
                      fontSize: "18px", fontWeight: 700, color: "var(--fg)",
                      letterSpacing: "0.02em",
                    }}>
                      {m.name}
                    </div>
                    <div style={{
                      fontSize: "13px", color: "var(--muted)", lineHeight: 1.5,
                      marginTop: "2px",
                    }}>
                      {m.role}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ━━ SLIDE 2: PREDICTION MARKETS 101 ━━ */}
        <PredictionMarketsSlide fintech={fintech} setFintech={setFintech} />

        {/* ━━ SLIDE 3: PROBLEM ━━ */}
        <ProblemSlide />

        {/* ━━ SLIDE 3: SOLUTION ━━ */}
        <SolutionSlide />

        {/* ━━ SLIDE 5: DEMO ━━ */}
        <section>
          <div className="term-bar">
            <span className="title">LIVE DEMO IN PROGRESS...</span>
            <span className="meta">DASHBOARD &middot; REAL-TIME</span>
          </div>
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", height: "88%", gap: "16px",
          }}>
            <img
              src="/assets/live_demo.png"
              alt="TradeMaxxer live demo"
              style={{
                maxWidth: "85%", maxHeight: "70%", objectFit: "contain",
                border: "1px solid var(--border)",
              }}
            />
          </div>
        </section>

        {/* ━━ SLIDE 6: ARCHITECTURE ━━ */}
        <ArchitectureSlide
          onModalReveal={() => {
            if (!modalRevealed) {
              setModalRevealed(true)
              setTimeout(() => {
                if (deckInstance.current) {
                  deckInstance.current.sync()
                  deckInstance.current.next()
                }
              }, 100)
            } else if (deckInstance.current) {
              deckInstance.current.next()
            }
          }}
          onSolanaReveal={() => {
            if (!solanaRevealed) {
              setSolanaRevealed(true)
              setTimeout(() => {
                if (deckInstance.current) {
                  deckInstance.current.sync()
                  deckInstance.current.next()
                }
              }, 100)
            } else if (deckInstance.current) {
              deckInstance.current.next()
            }
          }}
        />

        {/* ━━ SECRET: SOLANA DEEP DIVE ━━ */}
        {solanaRevealed && <SolanaDeepDive />}

        {/* ━━ SECRET: MODAL DEEP DIVE ━━ */}
        {modalRevealed && <ModalDeepDive />}

        {/* ━━ SLIDE 7: QUESTIONS / END ━━ */}
        <ClosingSlide />

      </div>
    </div>
    </FintechCtx.Provider>
  )
}
