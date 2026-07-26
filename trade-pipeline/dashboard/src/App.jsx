import { useState } from 'react'

// Kept intentionally minimal — one component, no router, no state library.
// See docs/DECISIONS.md "Minimal React... for the operational dashboard".
export default function App() {
  // In-memory only, not localStorage — a bearer token surviving in
  // persistent browser storage is unnecessary exposure for a demo ops
  // tool; losing it on page refresh (re-login required) is an acceptable
  // tradeoff here.
  const [token, setToken] = useState(null)
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('trade-pipeline-demo')
  const [loginError, setLoginError] = useState(null)

  const [trades, setTrades] = useState([])
  const [tradesError, setTradesError] = useState(null)

  const [flagName] = useState('enrichment_enabled')
  const [flagEnabled, setFlagEnabled] = useState(null)
  const [flagError, setFlagError] = useState(null)

  async function authedFetch(path, options = {}) {
    return fetch(path, {
      ...options,
      headers: { ...options.headers, Authorization: `Bearer ${token}` },
    })
  }

  async function login(event) {
    event.preventDefault()
    setLoginError(null)
    const resp = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!resp.ok) {
      setLoginError('Login failed — check username/password.')
      return
    }
    const data = await resp.json()
    setToken(data.access_token)
  }

  function logout() {
    setToken(null)
    setTrades([])
    setFlagEnabled(null)
  }

  async function loadTrades() {
    setTradesError(null)
    const resp = await authedFetch('/trades?limit=20')
    if (!resp.ok) {
      setTradesError(`Failed to load trades (${resp.status}).`)
      return
    }
    setTrades(await resp.json())
  }

  async function loadFlag() {
    setFlagError(null)
    const resp = await authedFetch(`/admin/feature-flags/${flagName}`)
    if (!resp.ok) {
      setFlagError(`Failed to load flag (${resp.status}).`)
      return
    }
    const data = await resp.json()
    setFlagEnabled(data.enabled)
  }

  async function toggleFlag() {
    setFlagError(null)
    const resp = await authedFetch(`/admin/feature-flags/${flagName}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !flagEnabled }),
    })
    if (!resp.ok) {
      setFlagError(`Failed to toggle flag (${resp.status}).`)
      return
    }
    const data = await resp.json()
    setFlagEnabled(data.enabled)
  }

  if (!token) {
    return (
      <main style={{ maxWidth: 360, margin: '4rem auto', fontFamily: 'sans-serif' }}>
        <h1>trade-pipeline dashboard</h1>
        <form onSubmit={login}>
          <div>
            <label>
              Username
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </label>
          </div>
          <div>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          </div>
          <button type="submit">Log in</button>
        </form>
        {loginError && <p style={{ color: 'crimson' }}>{loginError}</p>}
      </main>
    )
  }

  return (
    <main style={{ maxWidth: 720, margin: '2rem auto', fontFamily: 'sans-serif' }}>
      <h1>trade-pipeline dashboard</h1>
      <button onClick={logout}>Log out</button>

      <section>
        <h2>Feature flags</h2>
        <button onClick={loadFlag}>Load {flagName}</button>
        {flagEnabled !== null && (
          <p>
            {flagName}: <strong>{flagEnabled ? 'enabled' : 'disabled'}</strong>{' '}
            <button onClick={toggleFlag}>Toggle</button>
          </p>
        )}
        {flagError && <p style={{ color: 'crimson' }}>{flagError}</p>}
      </section>

      <section>
        <h2>Trades</h2>
        <button onClick={loadTrades}>Refresh</button>
        {tradesError && <p style={{ color: 'crimson' }}>{tradesError}</p>}
        <table border="1" cellPadding="4" style={{ borderCollapse: 'collapse', marginTop: 8 }}>
          <thead>
            <tr>
              <th>Broker</th>
              <th>Trade ID</th>
              <th>Symbol</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={`${t.broker_id}-${t.trade_id}`}>
                <td>{t.broker_id}</td>
                <td>{t.trade_id}</td>
                <td>{t.symbol}</td>
                <td>{t.qty}</td>
                <td>{t.price}</td>
                <td>{t.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <p>
        <a href="/docs" target="_blank" rel="noreferrer">API docs (Swagger)</a>
        {' · '}
        <a href="/metrics" target="_blank" rel="noreferrer">Metrics</a>
      </p>
    </main>
  )
}
