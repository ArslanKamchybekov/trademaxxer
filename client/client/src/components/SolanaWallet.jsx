import { useState, useEffect, useRef, useCallback } from "react"

const SOL_MINT = "So11111111111111111111111111111111111111112"
const USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
const SOL_DECIMALS = 9
const USDC_DECIMALS = 6
const INITIAL_USDC = 20
const CONTRACTS_PER_TRADE = 1
const PRICE_POLL_MS = 10_000
const FALLBACK_SOL_PRICE = 84.0

function genTxSig() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz123456789"
  let s = ""
  for (let i = 0; i < 44; i++) s += chars[Math.floor(Math.random() * chars.length)]
  return s
}

async function fetchSolPrice() {
  const res = await fetch(`https://lite-api.jup.ag/price/v3?ids=${SOL_MINT}`)
  if (!res.ok) throw new Error(`Price V3 ${res.status}`)
  const data = await res.json()
  return data[SOL_MINT]?.usdPrice ?? null
}

async function fetchJupiterQuote(inputMint, outputMint, amountBaseUnits) {
  const params = new URLSearchParams({
    inputMint,
    outputMint,
    amount: String(Math.round(amountBaseUnits)),
  })
  const res = await fetch(`https://lite-api.jup.ag/ultra/v1/order?${params}`)
  if (!res.ok) throw new Error(`Ultra API ${res.status}`)
  return res.json()
}

function shortName(question) {
  if (!question) return "???"
  const q = question.replace(/^Will\s+/i, "").replace(/\?$/, "")
  return q.length > 22 ? q.slice(0, 22) + "…" : q
}

function SwapRow({ swap }) {
  const isNew = Date.now() - swap.ts < 2000
  const priceDisplay = (swap.contractPrice * 100).toFixed(0)
  return (
    <div className={`px-2 py-[3px] text-[9px] border-b border-border/30 ${isNew ? "flash-news" : ""}`}>
      <div className="flex items-center gap-1.5">
        <span className={`font-bold shrink-0 ${swap.side === "BUY" ? "text-yes" : "text-no"}`}>
          {swap.side}
        </span>
        <span className="text-foreground/80 truncate">
          {swap.contracts}×{priceDisplay}¢
        </span>
        <span className="text-muted-foreground shrink-0">=</span>
        <span className="text-foreground/70 tabular shrink-0">${swap.costUsdc.toFixed(2)}</span>
        <span className="flex-1" />
        {swap.priceImpact != null && (
          <span className={`tabular shrink-0 ${Math.abs(swap.priceImpact) < 0.1 ? "text-muted-foreground" : "text-no"}`}>
            {swap.priceImpact.toFixed(2)}%
          </span>
        )}
        <span className="text-muted-foreground tabular shrink-0">
          {swap.latency}ms
        </span>
      </div>
      <div className="flex items-center gap-1 mt-0.5 text-[8px] text-muted-foreground/70">
        <span className="text-primary/50 shrink-0">JUP</span>
        {swap.route ? (
          <span className="truncate">${swap.costUsdc.toFixed(2)} → {swap.solAmount.toFixed(4)} SOL via {swap.route}</span>
        ) : (
          <span className="truncate">${swap.costUsdc.toFixed(2)} → {swap.solAmount.toFixed(4)} SOL</span>
        )}
      </div>
    </div>
  )
}

export default function SolanaWallet({ decisions, markets }) {
  const [usdc, setUsdc] = useState(INITIAL_USDC)
  const [positions, setPositions] = useState({})
  const [swaps, setSwaps] = useState([])
  const [solPrice, setSolPrice] = useState(FALLBACK_SOL_PRICE)
  const [priceSource, setPriceSource] = useState("...")
  const prevDecLen = useRef(0)
  const usdcRef = useRef(INITIAL_USDC)
  const tradeQueue = useRef([])
  const tradingRef = useRef(false)

  useEffect(() => { usdcRef.current = usdc }, [usdc])

  const deductUsdc = useCallback((cost) => {
    const newBalance = Math.max(0, usdcRef.current - cost)
    usdcRef.current = newBalance
    setUsdc(newBalance)
  }, [])

  // Poll Jupiter Price V3 for real SOL price
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const price = await fetchSolPrice()
        if (active && price != null) {
          setSolPrice(price)
          setPriceSource("jup")
        }
      } catch {
        if (active) setPriceSource("fallback")
      }
    }
    poll()
    const iv = setInterval(poll, PRICE_POLL_MS)
    return () => { active = false; clearInterval(iv) }
  }, [])

  const executeTrade = useCallback(async (d, market) => {
    const contractPrice = d.prev_price ?? market?.current_probability ?? 0.5
    const label = market ? shortName(market.question) : (d.marketId || d.market_address)?.slice(0, 8)
    const marketAddr = d.marketId || d.market_address || "unknown"
    const isBuy = d.action === "YES"
    const sharePrice = isBuy ? contractPrice : (1 - contractPrice)
    const costUsdc = CONTRACTS_PER_TRADE * sharePrice
    if (costUsdc <= 0 || usdcRef.current < costUsdc) return

    const amountBase = costUsdc * 10 ** USDC_DECIMALS
    let solAmount, route, priceImpact, latency

    try {
      const t0 = performance.now()
      const quote = await fetchJupiterQuote(USDC_MINT, SOL_MINT, amountBase)
      latency = Math.round(quote.totalTime ?? (performance.now() - t0))
      solAmount = Number(quote.outAmount) / 10 ** SOL_DECIMALS
      priceImpact = Number(quote.priceImpactPct ?? 0)
      route = (quote.routePlan || []).map(r => r.swapInfo?.label).filter(Boolean).join(" → ")
    } catch {
      solAmount = costUsdc / solPrice
      route = null
      priceImpact = null
      latency = 0
    }

    deductUsdc(costUsdc)
    setPositions(prev => {
      const existing = prev[marketAddr] || { contracts: 0, totalCost: 0, label }
      return {
        ...prev,
        [marketAddr]: {
          contracts: existing.contracts + CONTRACTS_PER_TRADE,
          totalCost: existing.totalCost + costUsdc,
          label,
          side: isBuy ? "YES" : "NO",
          currentPrice: contractPrice,
        },
      }
    })
    setSwaps(prev => [{
      id: Date.now() + Math.random(),
      side: isBuy ? "BUY" : "SELL",
      contracts: CONTRACTS_PER_TRADE,
      contractPrice: sharePrice,
      costUsdc,
      solAmount,
      sig: genTxSig(),
      market: label,
      ts: Date.now(),
      latency,
      route,
      priceImpact,
    }, ...prev].slice(0, 30))
  }, [solPrice, deductUsdc])

  const drainTradeQueue = useCallback(async () => {
    if (tradingRef.current) return
    tradingRef.current = true
    while (tradeQueue.current.length > 0) {
      const { decision, market } = tradeQueue.current.shift()
      await executeTrade(decision, market)
    }
    tradingRef.current = false
  }, [executeTrade])

  // Mark-to-market positions from every incoming decision (synchronous, never drops)
  useEffect(() => {
    if (decisions.length <= prevDecLen.current) {
      prevDecLen.current = decisions.length
      return
    }
    const newCount = decisions.length - prevDecLen.current
    prevDecLen.current = decisions.length
    const recent = decisions.slice(0, newCount)

    for (const d of recent) {
      const marketAddr = d.marketId || d.market_address || "unknown"
      const mtmPrice = d.theo
      if (mtmPrice != null) {
        setPositions(prev => {
          if (!prev[marketAddr]) return prev
          if (prev[marketAddr].currentPrice === mtmPrice) return prev
          return { ...prev, [marketAddr]: { ...prev[marketAddr], currentPrice: mtmPrice } }
        })
      }

      if (d.action === "YES" || d.action === "NO") {
        const market = markets.find(m => m.address === marketAddr)
        tradeQueue.current.push({ decision: d, market })
      }
    }

    drainTradeQueue()
  }, [decisions, markets, drainTradeQueue])

  const positionEntries = Object.entries(positions).filter(([, p]) => p.contracts > 0)
  const positionsValue = positionEntries.reduce((sum, [, p]) => {
    const price = p.side === "YES" ? p.currentPrice : (1 - p.currentPrice)
    return sum + p.contracts * price
  }, 0)
  const totalCostBasis = positionEntries.reduce((sum, [, p]) => sum + p.totalCost, 0)
  const pnl = positionsValue - totalCostBasis
  const pnlPct = totalCostBasis > 0 ? (pnl / totalCostBasis) * 100 : 0

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
            Jupiter Wallet
          </span>
          <span className="text-[8px] text-muted-foreground">Ultra API</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-muted-foreground">SOL</span>
          <span className="text-[9px] tabular text-foreground/70">
            ${solPrice.toFixed(2)}
          </span>
          {priceSource === "jup" && (
            <span className="w-1.5 h-1.5 rounded-full bg-yes/80" title="Live Jupiter price" />
          )}
          {priceSource === "fallback" && (
            <span className="w-1.5 h-1.5 rounded-full bg-no/60" title="Fallback price" />
          )}
        </div>
      </div>

      {/* Balances */}
      <div className="grid grid-cols-2 gap-px bg-border">
        <div className="bg-background px-2 py-1.5">
          <div className="text-[8px] uppercase text-muted-foreground tracking-wider">USDC</div>
          <div className="text-[13px] font-bold tabular text-foreground">
            ${usdc.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="bg-background px-2 py-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[8px] uppercase text-muted-foreground tracking-wider">Portfolio</div>
            <div className="flex items-center gap-1.5">
              <span className={`text-[9px] font-bold tabular ${pnl >= 0 ? "text-yes" : "text-no"}`}>
                {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}
              </span>
              <span className={`text-[8px] tabular ${pnl >= 0 ? "text-yes/60" : "text-no/60"}`}>
                ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)
              </span>
            </div>
          </div>
          <div className="text-[13px] font-bold tabular text-foreground">
            ${positionsValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[8px] tabular text-muted-foreground">
            {positionEntries.length} contract{positionEntries.length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

      {/* Swap ribbon header */}
      <div className="flex items-center justify-between px-2 py-0.5 border-b border-border">
        <span className="text-[8px] uppercase tracking-wider text-muted-foreground">
          Jupiter Swaps
        </span>
        <span className="text-[8px] tabular text-muted-foreground">
          {swaps.length} txns
        </span>
      </div>

      {/* Swap feed */}
      <div className="flex-1 overflow-y-auto">
        {swaps.length === 0 ? (
          <div className="px-2 py-4 text-center text-[9px] text-muted-foreground">
            Waiting for agent trades...
          </div>
        ) : (
          swaps.map(s => <SwapRow key={s.id} swap={s} />)
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-border px-2 py-0.5">
        <span className="text-[7px] text-muted-foreground">
          Solana Mainnet · lite-api.jup.ag
        </span>
        <div className="flex items-center gap-1.5">
          <span className="text-[7px] text-muted-foreground">
            {CONTRACTS_PER_TRADE} contracts/trade
          </span>
          <button
            onClick={() => { usdcRef.current += 1000; setUsdc(usdcRef.current) }}
            className="px-1.5 py-0 text-[7px] font-bold uppercase bg-yes/20 text-yes hover:bg-yes/30 border border-yes/30"
          >
            + $1k
          </button>
        </div>
      </div>
    </div>
  )
}
