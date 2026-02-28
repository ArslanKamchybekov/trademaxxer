import { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [news, setNews] = useState([])
  const [connectionStatus, setConnectionStatus] = useState('Connecting...')
  const [stats, setStats] = useState({ total: 0, bullish: 0, bearish: 0, neutral: 0 })
  const ws = useRef(null)

  useEffect(() => {
    // Connect to WebSocket server
    const connectWebSocket = () => {
      ws.current = new WebSocket('ws://localhost:8765')

      ws.current.onopen = () => {
        setConnectionStatus('Connected')
        console.log('Connected to news stream')
      }

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)

          if (message.type === 'news') {
            const newsItem = message.data

            // Add timestamp for display
            newsItem.displayTime = new Date().toLocaleTimeString()

            // Add to beginning of array (latest first)
            setNews(prevNews => [newsItem, ...prevNews.slice(0, 49)]) // Keep last 50 items

            // Update stats
            setStats(prevStats => ({
              total: prevStats.total + 1,
              bullish: prevStats.bullish + (newsItem.sentiment === 'bullish' ? 1 : 0),
              bearish: prevStats.bearish + (newsItem.sentiment === 'bearish' ? 1 : 0),
              neutral: prevStats.neutral + (newsItem.sentiment === 'neutral' ? 1 : 0),
            }))
          } else if (message.type === 'connected') {
            console.log('Welcome message:', message.message)
          }
        } catch (error) {
          console.error('Error parsing message:', error)
        }
      }

      ws.current.onclose = () => {
        setConnectionStatus('Disconnected')
        console.log('Disconnected from news stream')
        // Try to reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000)
      }

      ws.current.onerror = (error) => {
        setConnectionStatus('Error')
        console.error('WebSocket error:', error)
      }
    }

    connectWebSocket()

    // Cleanup on unmount
    return () => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [])

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'bullish': return '#10b981' // green
      case 'bearish': return '#ef4444' // red
      case 'neutral': return '#6b7280' // gray
      default: return '#6b7280'
    }
  }

  const getUrgencyIcon = (urgency) => {
    switch (urgency) {
      case 'breaking': return '🚨'
      case 'high': return '⚡'
      default: return '📰'
    }
  }

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  return (
    <div className="app">
      <header className="header">
        <h1>📈 Live News Stream</h1>
        <div className="connection-status" data-status={connectionStatus.toLowerCase()}>
          <span className="status-dot"></span>
          {connectionStatus}
        </div>
      </header>

      <div className="stats">
        <div className="stat-item">
          <span className="stat-value">{stats.total}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="stat-item bullish">
          <span className="stat-value">{stats.bullish}</span>
          <span className="stat-label">Bullish</span>
        </div>
        <div className="stat-item bearish">
          <span className="stat-value">{stats.bearish}</span>
          <span className="stat-label">Bearish</span>
        </div>
        <div className="stat-item neutral">
          <span className="stat-value">{stats.neutral}</span>
          <span className="stat-label">Neutral</span>
        </div>
      </div>

      <div className="news-container">
        {news.length === 0 ? (
          <div className="no-news">
            <p>Waiting for live news...</p>
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        ) : (
          news.map((item) => (
            <div key={item.id} className="news-item">
              <div className="news-header">
                <span className="urgency-icon">
                  {getUrgencyIcon(item.urgency)}
                </span>
                <span className="news-time">
                  {formatTimestamp(item.timestamp)}
                </span>
                <span
                  className="sentiment-badge"
                  style={{ backgroundColor: getSentimentColor(item.sentiment) }}
                >
                  {item.sentiment || 'neutral'}
                </span>
              </div>

              <h3 className="news-headline">{item.headline}</h3>

              {item.body && (
                <p className="news-body">{item.body}</p>
              )}

              <div className="news-meta">
                <span className="news-source">
                  📡 {item.sourceHandle} ({item.sourceType})
                </span>

                {item.tickers && item.tickers.length > 0 && (
                  <div className="tickers">
                    {item.tickers.slice(0, 5).map(ticker => (
                      <span key={ticker} className="ticker">
                        ${ticker}
                      </span>
                    ))}
                    {item.tickers.length > 5 && (
                      <span className="ticker-more">
                        +{item.tickers.length - 5} more
                      </span>
                    )}
                  </div>
                )}

                {item.categories && item.categories.length > 0 && (
                  <div className="categories">
                    {item.categories.map(category => (
                      <span key={category} className="category">
                        {category}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default App