import { useState, useEffect } from "react"

export default function OrderTicket({
  markets,
  marketStats,
  onPlaceOrder,
  mode = "manual" // "manual" or "agent"
}) {
  const [selectedMarket, setSelectedMarket] = useState(null)
  const [orderSide, setOrderSide] = useState("YES") // "YES" or "NO"
  const [orderSize, setOrderSize] = useState("100")
  const [executionVenue, setExecutionVenue] = useState("simulation") // "simulation", "kairos", "dflow"
  const [marketSource, setMarketSource] = useState("kalshi") // "kalshi" or "dflow"
  const [dflowMarkets, setDflowMarkets] = useState([])
  const [dflowLoading, setDflowLoading] = useState(false)

  // Fetch DFlow markets
  useEffect(() => {
    const fetchDFlowMarkets = async () => {
      if (marketSource === "dflow") {
        try {
          setDflowLoading(true)
          const response = await fetch('http://localhost:8767/api/dflow-markets')
          if (!response.ok) throw new Error('Failed to fetch DFlow markets')
          const data = await response.json()
          setDflowMarkets(data.markets)
        } catch (error) {
          console.error('Error fetching DFlow markets:', error)
          setDflowMarkets([])
        } finally {
          setDflowLoading(false)
        }
      }
    }

    fetchDFlowMarkets()
  }, [marketSource])

  // Filter to markets that have pricing data
  const tradableMarkets = markets.filter(market => {
    const stats = marketStats[market.address]
    return market.current_probability > 0
  })

  // Get current market list based on source
  const currentMarkets = marketSource === "dflow" ? dflowMarkets : tradableMarkets

  const handlePlaceOrder = async () => {
    if (!selectedMarket) return

    const order = {
      market: selectedMarket,
      side: orderSide,
      size: parseFloat(orderSize),
      price: selectedMarket.current_probability,
      timestamp: Date.now(),
      mode: mode,
      venue: executionVenue
    }

    // Execute based on venue
    if (executionVenue === "dflow" || marketSource === "dflow") {
      try {
        // For DFlow markets, use the dflow_market_id, otherwise use address
        const marketId = marketSource === "dflow" ? selectedMarket.dflow_market_id : selectedMarket.address

        const response = await fetch('http://localhost:8767/api/execute-trade', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            market_id: marketId,
            side: orderSide,
            size: parseFloat(orderSize)
          })
        })

        const result = await response.json()

        if (result.success) {
          console.log('DFlow trade executed:', result)
          // Add DFlow-specific data to order
          order.tx_hash = result.tx_hash
          order.venue = 'dflow'
          order.dflow_market_id = result.dflow_market_id
        } else {
          console.error('DFlow trade failed:', result.error)
          alert(`Trade failed: ${result.error}`)
          return
        }
      } catch (error) {
        console.error('DFlow execution error:', error)
        alert(`Trade execution error: ${error.message}`)
        return
      }
    } else if (executionVenue === "kairos") {
      // Future: Kairos execution (currently simulation only)
      console.log('Kairos execution not yet implemented, using simulation')
      order.venue = 'simulation'
    }

    onPlaceOrder?.(order)

    // Reset form
    setSelectedMarket(null)
    setOrderSize("100")
  }

  const getTheoPrice = (market) => {
    const stats = marketStats[market.address]
    if (!stats || !stats.avgConf) return null

    // Simple theo calculation: adjust market price by confidence
    const confidence = stats.avgConf
    const marketPrice = market.current_probability

    if (stats.lastAction === "YES") {
      return Math.min(0.95, marketPrice + (confidence * 0.1))
    } else if (stats.lastAction === "NO") {
      return Math.max(0.05, marketPrice - (confidence * 0.1))
    }

    return marketPrice
  }

  const formatPrice = (price) => {
    return `${(price * 100).toFixed(1)}¢`
  }

  if (mode === "agent") {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-border px-2 py-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
            Agent Trades
          </span>
          <span className="ml-2 text-[8px] text-muted-foreground">
            Live Activity
          </span>
        </div>

        <div className="flex-1 overflow-hidden p-2">
          {/* Agent Trade Feed */}
          <div className="space-y-2 max-h-full overflow-y-auto">
            {tradableMarkets
              .filter(m => marketStats[m.address]?.lastAction && marketStats[m.address]?.lastAction !== "SKIP")
              .slice(0, 8)
              .map(market => {
                const stats = marketStats[market.address]
                const action = stats.lastAction
                const conf = stats.avgConf || 0
                const actualPrice = action === "YES" ? market.current_probability : (1 - market.current_probability)
                const theoPrice = getTheoPrice(market)
                const theoForSide = action === "YES" ? theoPrice : (1 - theoPrice)
                const edge = theoForSide && actualPrice ? ((theoForSide - actualPrice) / actualPrice * 100) : 0

                return (
                  <div key={market.address} className="text-[9px] p-2 bg-muted/20 rounded border border-border/30">
                    {/* Trade Header */}
                    <div className="flex justify-between items-center mb-1">
                      <span className={`font-bold ${action === "YES" ? "text-yes" : "text-no"}`}>
                        {action} TRADE
                      </span>
                      <span className="text-muted-foreground">
                        {(conf * 100).toFixed(0)}% conf
                      </span>
                    </div>

                    {/* Market */}
                    <div className="text-[8px] text-foreground/80 mb-1.5 line-clamp-2">
                      {market.question}
                    </div>

                    {/* Price Comparison */}
                    <div className="space-y-0.5">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Actual:</span>
                        <span className="font-mono">{formatPrice(actualPrice)}</span>
                      </div>
                      {theoPrice && (
                        <>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Theo:</span>
                            <span className="font-mono text-amber">{formatPrice(theoForSide)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Edge:</span>
                            <span className={`font-mono text-[8px] ${edge > 0 ? "text-yes" : edge < 0 ? "text-no" : "text-muted-foreground"}`}>
                              {edge > 0 ? "+" : ""}{edge.toFixed(1)}%
                            </span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Trade Details */}
                    <div className="mt-1.5 pt-1 border-t border-border/20">
                      <div className="flex justify-between text-[8px] text-muted-foreground">
                        <span>Size: $100</span>
                        <span>Status: FILLED</span>
                      </div>
                    </div>
                  </div>
                )
              })}

            {/* Empty State */}
            {tradableMarkets.filter(m => marketStats[m.address]?.lastAction && marketStats[m.address]?.lastAction !== "SKIP").length === 0 && (
              <div className="text-center text-[10px] text-muted-foreground mt-4">
                <div className="mb-2">Agents monitoring markets</div>
                <div>Waiting for trading opportunities...</div>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Manual Trading
        </span>
        <span className="ml-2 text-[8px] text-muted-foreground">
          Order Ticket
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {/* Market Source Selection */}
        <div>
          <label className="text-[9px] uppercase text-muted-foreground">
            Market Source
          </label>
          <div className="flex mt-1 gap-1">
            <button
              onClick={() => {
                setMarketSource("kalshi")
                setSelectedMarket(null)
              }}
              className={`flex-1 py-1 px-2 text-[10px] rounded transition-colors ${
                marketSource === "kalshi"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              Kalshi
            </button>
            <button
              onClick={() => {
                setMarketSource("dflow")
                setSelectedMarket(null)
                setExecutionVenue("dflow") // Auto-set to DFlow when switching to DFlow markets
              }}
              className={`flex-1 py-1 px-2 text-[10px] rounded transition-colors ${
                marketSource === "dflow"
                  ? "bg-amber text-black"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              DFlow
            </button>
          </div>
          <div className="mt-1 text-[8px] text-muted-foreground">
            {marketSource === "kalshi" && `${tradableMarkets.length} markets available`}
            {marketSource === "dflow" && (
              dflowLoading ? "Loading..." : `${dflowMarkets.length} markets available`
            )}
          </div>
        </div>

        {/* Market Selection */}
        <div>
          <label className="text-[9px] uppercase text-muted-foreground">
            Market
          </label>
          <select
            value={selectedMarket?.[marketSource === "dflow" ? "dflow_market_id" : "address"] || ""}
            onChange={(e) => {
              const market = currentMarkets.find(m =>
                (marketSource === "dflow" ? m.dflow_market_id : m.address) === e.target.value
              )
              setSelectedMarket(market)
            }}
            className="w-full mt-1 text-[10px] bg-background border border-border rounded px-2 py-1"
            disabled={dflowLoading}
          >
            <option value="">
              {dflowLoading ? "Loading markets..." : "Select market..."}
            </option>
            {currentMarkets.map(market => (
              <option
                key={marketSource === "dflow" ? market.dflow_market_id : market.address}
                value={marketSource === "dflow" ? market.dflow_market_id : market.address}
              >
                {market.question.slice(0, 40)}...
              </option>
            ))}
          </select>
        </div>

        {selectedMarket && (
          <>
            {/* Execution Venue Selection */}
            <div>
              <label className="text-[9px] uppercase text-muted-foreground">
                Execution Venue
              </label>
              <select
                value={executionVenue}
                onChange={(e) => setExecutionVenue(e.target.value)}
                className="w-full mt-1 text-[10px] bg-background border border-border rounded px-2 py-1"
              >
                <option value="simulation">Simulation</option>
                <option value="dflow">DFlow (On-Chain)</option>
                <option value="kairos" disabled>Kairos (Coming Soon)</option>
              </select>
              <div className="mt-1 text-[8px] text-muted-foreground">
                {executionVenue === "simulation" && "Practice trading with virtual funds"}
                {executionVenue === "dflow" && "Execute real trades on Solana via DFlow"}
                {executionVenue === "kairos" && "Execute real trades via Kairos API"}
              </div>
            </div>

            {/* Pricing Display */}
            <div className={`rounded p-2 space-y-1 ${
              executionVenue === "dflow" || marketSource === "dflow" ? "bg-amber/10 border border-amber/30" :
              executionVenue === "kairos" ? "bg-blue/10 border border-blue/30" :
              "bg-muted/20"
            }`}>
              <div className="flex justify-between text-[10px]">
                <span>YES Price:</span>
                <span className="font-mono text-yes">
                  {formatPrice(selectedMarket.current_probability || 0.5)}
                </span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span>NO Price:</span>
                <span className="font-mono text-no">
                  {formatPrice(1 - (selectedMarket.current_probability || 0.5))}
                </span>
              </div>
              {marketSource === "dflow" && (
                <div className="text-[8px] text-amber border-t border-amber/30 pt-1">
                  <div>🔗 On-chain market via DFlow Protocol</div>
                  <div>Market ID: {selectedMarket.dflow_market_id}</div>
                  {selectedMarket.mapped_kalshi_ticker && (
                    <div>↔ Mapped to {selectedMarket.mapped_kalshi_ticker}</div>
                  )}
                </div>
              )}
              {getTheoPrice(selectedMarket) && (
                <>
                  <div className="border-t border-border/30 pt-1">
                    <div className="flex justify-between text-[10px]">
                      <span>Theo YES:</span>
                      <span className="font-mono text-amber">
                        {formatPrice(getTheoPrice(selectedMarket))}
                      </span>
                    </div>
                    <div className="flex justify-between text-[10px]">
                      <span>Theo NO:</span>
                      <span className="font-mono text-amber">
                        {formatPrice(1 - getTheoPrice(selectedMarket))}
                      </span>
                    </div>
                  </div>
                </>
              )}
              {marketStats[selectedMarket.address]?.lastAction && (
                <div className="flex justify-between text-[10px] border-t border-border/30 pt-1">
                  <span>Agent Signal:</span>
                  <span className={
                    marketStats[selectedMarket.address].lastAction === "YES"
                      ? "text-yes"
                      : marketStats[selectedMarket.address].lastAction === "NO"
                      ? "text-no"
                      : "text-muted-foreground"
                  }>
                    {marketStats[selectedMarket.address].lastAction}
                  </span>
                </div>
              )}
            </div>

            {/* Order Side */}
            <div>
              <label className="text-[9px] uppercase text-muted-foreground">
                Direction
              </label>
              <div className="flex mt-1 gap-1">
                <button
                  onClick={() => setOrderSide("YES")}
                  className={`flex-1 py-1 px-2 text-[10px] rounded transition-colors ${
                    orderSide === "YES"
                      ? "bg-yes text-white"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  YES
                </button>
                <button
                  onClick={() => setOrderSide("NO")}
                  className={`flex-1 py-1 px-2 text-[10px] rounded transition-colors ${
                    orderSide === "NO"
                      ? "bg-no text-white"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  NO
                </button>
              </div>
              {selectedMarket && (
                <div className="mt-1 text-[9px] text-muted-foreground">
                  @ {orderSide === "YES"
                    ? formatPrice(selectedMarket.current_probability || 0.5)
                    : formatPrice(1 - (selectedMarket.current_probability || 0.5))
                  }
                </div>
              )}
            </div>

            {/* Order Size */}
            <div>
              <label className="text-[9px] uppercase text-muted-foreground">
                Size ($)
              </label>
              <input
                type="number"
                value={orderSize}
                onChange={(e) => setOrderSize(e.target.value)}
                className="w-full mt-1 text-[10px] bg-background border border-border rounded px-2 py-1"
                placeholder="100"
                min="1"
                max="10000"
              />
            </div>

            {/* Submit Button */}
            <div>
              {executionVenue === "dflow" && (
                <div className="mb-2 p-2 bg-amber/10 border border-amber/30 rounded text-[9px] text-amber">
                  ⚠️ Real on-chain transaction using Solana
                </div>
              )}
              <button
                onClick={handlePlaceOrder}
                disabled={!selectedMarket || !orderSize}
                className={`w-full py-2 px-2 text-[10px] font-bold uppercase rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all ${
                  executionVenue === "dflow" ? "bg-amber text-black" :
                  executionVenue === "kairos" ? "bg-blue text-white" :
                  "bg-primary text-primary-foreground"
                }`}
              >
                {executionVenue === "dflow" ? "Execute On-Chain" :
                 executionVenue === "kairos" ? "Execute Live" :
                 "Place Simulation Order"}
              </button>
            </div>
          </>
        )}

        {/* Quick Actions */}
        {!selectedMarket && currentMarkets.length > 0 && (
          <div>
            <div className="text-[9px] uppercase text-muted-foreground mb-2">
              Quick Trade
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {currentMarkets.slice(0, 3).map(market => (
                <button
                  key={marketSource === "dflow" ? market.dflow_market_id : market.address}
                  onClick={() => setSelectedMarket(market)}
                  className="w-full text-left p-1 text-[10px] bg-muted/30 hover:bg-muted/50 rounded transition-colors"
                >
                  <div className="truncate">
                    {market.question.slice(0, 35)}...
                  </div>
                  <div className="text-[9px] text-muted-foreground">
                    {formatPrice(market.current_probability || 0.5)}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}