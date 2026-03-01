import { useState, useEffect } from 'react'

export default function DFlowWallet() {
  const [walletData, setWalletData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Fetch DFlow wallet data
  useEffect(() => {
    const fetchWalletData = async () => {
      try {
        setLoading(true)
        const response = await fetch('http://localhost:8767/api/wallet')
        if (!response.ok) throw new Error('Failed to fetch wallet data')
        const data = await response.json()
        setWalletData(data)
        setError(null)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchWalletData()

    // Refresh data every 30 seconds
    const interval = setInterval(fetchWalletData, 30000)
    return () => clearInterval(interval)
  }, [])

  const formatAddress = (address) => {
    if (!address) return 'N/A'
    return `${address.slice(0, 6)}...${address.slice(-4)}`
  }

  if (loading) {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-border px-2 py-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
            DFlow Wallet
          </span>
          <span className="ml-2 text-[8px] text-muted-foreground">
            On-Chain
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-[10px] text-muted-foreground">Loading...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-border px-2 py-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
            DFlow Wallet
          </span>
          <span className="ml-2 text-[8px] text-no">
            Offline
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <div className="text-[10px] text-no mb-1">Connection Failed</div>
            <div className="text-[8px] text-muted-foreground">{error}</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          DFlow Wallet
        </span>
        <span className="ml-2 text-[8px] text-muted-foreground">
          Solana Mainnet
        </span>
      </div>

      {/* Wallet Address */}
      <div className="border-b border-border px-2 py-1.5">
        <div className="text-[8px] uppercase text-muted-foreground tracking-wider mb-1">
          Wallet Address
        </div>
        <div className="text-[9px] font-mono text-foreground/80">
          {formatAddress(walletData?.wallet)}
        </div>
        {walletData?.wallet && (
          <button
            onClick={() => navigator.clipboard.writeText(walletData.wallet)}
            className="text-[7px] text-primary hover:text-primary/80 mt-1"
          >
            Copy Full Address
          </button>
        )}
      </div>

      {/* SOL Balance */}
      <div className="border-b border-border px-2 py-1.5">
        <div className="text-[8px] uppercase text-muted-foreground tracking-wider mb-1">
          SOL Balance
        </div>
        <div className="text-[13px] font-bold tabular text-foreground">
          {walletData?.sol_balance?.toFixed(4) || '0.0000'} SOL
        </div>
        <div className="text-[8px] text-muted-foreground">
          {walletData?.sol_balance === 0 && "⚠️ No funds available for trading"}
        </div>
      </div>

      {/* Trading Status */}
      <div className="flex-1 overflow-y-auto px-2 py-1.5">
        <div className="text-[8px] uppercase text-muted-foreground tracking-wider mb-2">
          Trading Status
        </div>
        <div className="space-y-2">
          <div className="p-2 bg-muted/20 rounded border border-border/30">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[9px] text-foreground/80">Test Mode</span>
              <span className="text-[8px] font-mono text-amber">Active</span>
            </div>
            <div className="text-[8px] text-muted-foreground">
              Simulated trades (no SOL required)
            </div>
          </div>

          <div className="p-2 bg-muted/20 rounded border border-border/30">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[9px] text-foreground/80">On-Chain Ready</span>
              <span className={`text-[8px] font-mono ${walletData?.sol_balance > 0 ? "text-yes" : "text-muted-foreground"}`}>
                {walletData?.sol_balance > 0 ? "Yes" : "Fund Wallet"}
              </span>
            </div>
            <div className="text-[8px] text-muted-foreground">
              Real blockchain execution
            </div>
          </div>
        </div>
      </div>

      {/* Status Footer */}
      <div className="border-t border-border px-2 py-0.5">
        <div className="flex items-center justify-between">
          <span className="text-[7px] text-muted-foreground">
            DFlow Protocol · Solana
          </span>
          <div className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${
              walletData ? "bg-yes/80" : "bg-no/60"
            }`} />
            <span className="text-[7px] text-muted-foreground">
              {walletData ? "Connected" : "Offline"}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}