import { useState, useEffect, useRef, useCallback } from "react"

const WS_URL = "ws://localhost:8765"
const RECONNECT_MS = 2000
const MAX_NEWS = 200
const MAX_DECISIONS = 200
const MAX_LATENCY_POINTS = 120
const MAX_THROUGHPUT_POINTS = 120
const MAX_VELOCITY_POINTS = 60
const THROUGHPUT_INTERVAL_MS = 1000

// Simple English language detection - checks for common English words and patterns
const isEnglish = (text) => {
  if (!text) return false

  const englishWords = [
    'the', 'and', 'or', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'can', 'may', 'might', 'must', 'shall', 'to', 'of', 'in', 'on', 'at', 'by',
    'for', 'with', 'without', 'from', 'as', 'than', 'that', 'this', 'these',
    'those', 'it', 'its', 'he', 'she', 'his', 'her', 'him', 'them', 'they'
  ]

  const words = text.toLowerCase().split(/\s+/)
  const englishWordCount = words.filter(word =>
    englishWords.includes(word.replace(/[^\w]/g, ''))
  ).length

  // Consider it English if at least 20% of words are common English words
  // and there are at least 3 words total
  return words.length >= 3 && (englishWordCount / words.length) >= 0.2
}

export default function useWebSocket() {
  const [status, setStatus] = useState("DISCONNECTED")
  const [news, setNews] = useState([])
  const [decisions, setDecisions] = useState([])
  const [latencyData, setLatencyData] = useState([])
  const [throughputData, setThroughputData] = useState([])
  const [velocityData, setVelocityData] = useState([])
  const [stats, setStats] = useState({
    events: 0,
    decisions: 0,
    yes: 0,
    no: 0,
    skip: 0,
    totalLatency: 0,
    avgLatency: 0,
    minLatency: Infinity,
    maxLatency: 0,
    latencies: [],
    confidences: [],
  })
  const [marketStats, setMarketStats] = useState({})
  const [tagStats, setTagStats] = useState({})
  const [sessionStart] = useState(Date.now())
  const [enabledMarkets, setEnabledMarkets] = useState(new Set())
  const [markets, setMarkets] = useState([])

  const ws = useRef(null)
  const seqRef = useRef(0)
  const reconnectTimer = useRef(null)
  const throughputCounter = useRef({ events: 0, decisions: 0 })

  // Rolling throughput sampler
  useEffect(() => {
    const id = setInterval(() => {
      const { events, decisions } = throughputCounter.current
      throughputCounter.current = { events: 0, decisions: 0 }
      const t = Date.now()
      setThroughputData((prev) => [
        ...prev.slice(-(MAX_THROUGHPUT_POINTS - 1)),
        { t, eps: events, dps: decisions },
      ])
    }, THROUGHPUT_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  // News velocity sampler (events per 5-second bucket)
  useEffect(() => {
    const id = setInterval(() => {
      setNews((current) => {
        const now = Date.now()
        const windowMs = 5000
        const recent = current.filter((n) => now - n._ts < windowMs).length
        const rate = (recent / (windowMs / 1000)).toFixed(1)
        setVelocityData((prev) => [
          ...prev.slice(-(MAX_VELOCITY_POINTS - 1)),
          { t: now, rate: parseFloat(rate) },
        ])
        return current
      })
    }, 2000)
    return () => clearInterval(id)
  }, [])

  const handleNews = useCallback((item) => {
    // Filter out non-English news
    if (!isEnglish(item.headline)) {
      return // Skip non-English news
    }

    // Prevent duplicate news items using id
    setNews((prev) => {
      // Check if item already exists
      if (prev.some(existingItem => existingItem.id === item.id)) {
        return prev // Don't add duplicate
      }

      // Add new item
      item._seq = ++seqRef.current
      item._ts = Date.now()
      return [item, ...prev.slice(0, MAX_NEWS - 1)]
    })

    setStats((prev) => ({ ...prev, events: prev.events + 1 }))
    throughputCounter.current.events++

    const cats = item.categories || []
    if (cats.length > 0) {
      setTagStats((prev) => {
        const next = { ...prev }
        for (const c of cats) {
          next[c] = (next[c] || 0) + 1
        }
        return next
      })
    }
  }, [])

  const handleDecision = useCallback((data) => {
    data._seq = ++seqRef.current
    data._ts = Date.now()
    setDecisions((prev) => [data, ...prev.slice(0, MAX_DECISIONS - 1)])
    throughputCounter.current.decisions++

    const action = data.action
    const lat = data.latency_ms || 0
    const conf = data.confidence || 0

    setStats((prev) => {
      const newDecisions = prev.decisions + 1
      const newTotalLatency = prev.totalLatency + lat
      const newLatencies = [...prev.latencies.slice(-199), lat]
      const newConfidences = [...prev.confidences.slice(-499), conf]
      return {
        ...prev,
        decisions: newDecisions,
        yes: prev.yes + (action === "YES" ? 1 : 0),
        no: prev.no + (action === "NO" ? 1 : 0),
        skip: prev.skip + (action === "SKIP" ? 1 : 0),
        totalLatency: newTotalLatency,
        avgLatency: newTotalLatency / newDecisions,
        minLatency: Math.min(prev.minLatency, lat),
        maxLatency: Math.max(prev.maxLatency, lat),
        latencies: newLatencies,
        confidences: newConfidences,
      }
    })

    if (lat) {
      setLatencyData((prev) => [
        ...prev.slice(-(MAX_LATENCY_POINTS - 1)),
        { t: Date.now(), ms: Math.round(lat) },
      ])
    }

    setMarketStats((prev) => {
      const addr = data.market_address || "unknown"
      const existing = prev[addr] || {
        yes: 0, no: 0, skip: 0,
        lastAction: null, lastLatency: 0,
        totalConf: 0, totalSignals: 0,
        confidences: [], latencies: [],
        pnl: 0,
      }
      const newSignals = existing.totalSignals + 1
      const newTotalConf = existing.totalConf + conf
      const pnlDelta = action === "YES" ? conf * 100 : action === "NO" ? -conf * 50 : 0
      return {
        ...prev,
        [addr]: {
          yes: existing.yes + (action === "YES" ? 1 : 0),
          no: existing.no + (action === "NO" ? 1 : 0),
          skip: existing.skip + (action === "SKIP" ? 1 : 0),
          lastAction: action,
          lastLatency: lat,
          totalConf: newTotalConf,
          totalSignals: newSignals,
          avgConf: newTotalConf / newSignals,
          confidences: [...existing.confidences.slice(-29), conf],
          latencies: [...existing.latencies.slice(-29), lat],
          pnl: existing.pnl + pnlDelta,
        },
      }
    })
  }, [])

  const toggleMarket = useCallback((address) => {
    const nowEnabled = !enabledMarkets.has(address)
    setEnabledMarkets((prev) => {
      const next = new Set(prev)
      if (nowEnabled) next.add(address)
      else next.delete(address)
      return next
    })
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        type: "toggle_market",
        address,
        enabled: nowEnabled,
      }))
    }
  }, [enabledMarkets])

  useEffect(() => {
    const connect = () => {
      if (ws.current?.readyState === WebSocket.OPEN) return

      setStatus("CONNECTING")
      const socket = new WebSocket(WS_URL)
      ws.current = socket

      socket.onopen = () => setStatus("CONNECTED")

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === "news") handleNews(msg.data)
          else if (msg.type === "decision") handleDecision(msg.data)
          else if (msg.type === "connected" && msg.markets_state) {
            setMarkets(msg.markets_state.markets || [])
            setEnabledMarkets(new Set(msg.markets_state.enabled || []))
          } else if (msg.type === "markets_state" && msg.data) {
            setMarkets(msg.data.markets || [])
            setEnabledMarkets(new Set(msg.data.enabled || []))
          }
        } catch {}
      }

      socket.onclose = () => {
        setStatus("DISCONNECTED")
        reconnectTimer.current = setTimeout(connect, RECONNECT_MS)
      }

      socket.onerror = () => setStatus("ERROR")
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [handleNews, handleDecision])

  return {
    status, news, decisions,
    latencyData, throughputData, velocityData,
    stats, marketStats, tagStats, sessionStart,
    enabledMarkets, toggleMarket, markets,
  }
}
