import { useState, useEffect } from 'react'
import axios from 'axios'

/**
 * QueryInput — Search box with component filter and submit button.
 */
export default function QueryInput({ onResult, onLoading }) {
  const [query, setQuery] = useState('')
  const [component, setComponent] = useState('')
  const [components, setComponents] = useState([])
  const [loading, setLoading] = useState(false)

  // Fetch available components
  useEffect(() => {
    const fetchComponents = async () => {
      try {
        const res = await axios.get('/api/components')
        setComponents(res.data.components || [])
      } catch {
        // Not critical — selector will be empty
      }
    }
    fetchComponents()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    if (onLoading) onLoading(true)

    try {
      const res = await axios.post('/api/query', {
        query: query.trim(),
        component: component,
      })
      if (onResult) onResult(res.data)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      if (onResult) onResult({ type: 'text', data: { message: `Error: ${msg}` }, source: 'error' })
    } finally {
      setLoading(false)
      if (onLoading) onLoading(false)
    }
  }

  return (
    <div className="glass-card animate-fade-in-up" style={{ animationDelay: '200ms' }}>
      <div className="card-header">
        <div className="card-icon">🔍</div>
        <h2>Query Datasheet</h2>
      </div>

      <form className="query-form" onSubmit={handleSubmit} id="query-form">
        <div className="query-input-wrapper">
          <span className="search-icon">⚡</span>
          <input
            id="query-input"
            className="query-input"
            type="text"
            placeholder="Ask about any parameter, feature, or specification…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
          />
        </div>
        <button
          id="query-submit-btn"
          className="query-btn"
          type="submit"
          disabled={loading || !query.trim()}
        >
          {loading && <span className="spinner" />}
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {components.length > 0 && (
        <div className="component-selector">
          <span>Filter by component:</span>
          <select
            id="component-selector"
            value={component}
            onChange={(e) => setComponent(e.target.value)}
          >
            <option value="">All components</option>
            {components.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}
