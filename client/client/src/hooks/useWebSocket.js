import { useState, useEffect, useRef, useCallback } from "react"

const WS_URL = "ws://localhost:8765"
const RECONNECT_MS = 2000
const MAX_NEWS = 200
const MAX_DECISIONS = 200
const MAX_LATENCY_POINTS = 60

export default function useWebSocket() {
  const [status, setStatus] = useState("DISCONNECTED")
  const [news, setNews] = useState([])
  const [decisions, setDecisions] = useState([])
  const [latencyData, setLatencyData] = useState([])
  const [stats, setStats] = useState({
    events: 0,
    decisions: 0,
    yes: 0,
    no: 0,
    skip: 0,
    totalLatency: 0,
    avgLatency: 0,
  })
  const [marketStats, setMarketStats] = useState({})

  const ws = useRef(null)
  const seqRef = useRef(0)
  const reconnectTimer = useRef(null)

  const handleNews = useCallback((item) => {
    item._seq = ++seqRef.current
    item._ts = Date.now()
    setNews((prev) => [item, ...prev.slice(0, MAX_NEWS - 1)])
    setStats((prev) => ({
      ...prev,
      events: prev.events + 1,
    }))
  }, [])

  const handleDecision = useCallback((data) => {
    data._seq = ++seqRef.current
    data._ts = Date.now()
    setDecisions((prev) => [data, ...prev.slice(0, MAX_DECISIONS - 1)])

    const action = data.action
    setStats((prev) => {
      const newDecisions = prev.decisions + 1
      const newTotalLatency = prev.totalLatency + (data.latency_ms || 0)
      return {
        ...prev,
        decisions: newDecisions,
        yes: prev.yes + (action === "YES" ? 1 : 0),
        no: prev.no + (action === "NO" ? 1 : 0),
        skip: prev.skip + (action === "SKIP" ? 1 : 0),
        totalLatency: newTotalLatency,
        avgLatency: newTotalLatency / newDecisions,
      }
    })

    if (data.latency_ms) {
      setLatencyData((prev) => [
        ...prev.slice(-(MAX_LATENCY_POINTS - 1)),
        { t: Date.now(), ms: Math.round(data.latency_ms) },
      ])
    }

    setMarketStats((prev) => {
      const addr = data.market_address || "unknown"
      const existing = prev[addr] || { yes: 0, no: 0, skip: 0, lastAction: null, lastLatency: 0 }
      return {
        ...prev,
        [addr]: {
          yes: existing.yes + (action === "YES" ? 1 : 0),
          no: existing.no + (action === "NO" ? 1 : 0),
          skip: existing.skip + (action === "SKIP" ? 1 : 0),
          lastAction: action,
          lastLatency: data.latency_ms || 0,
        },
      }
    })
  }, [])

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

  return { status, news, decisions, latencyData, stats, marketStats }
}
