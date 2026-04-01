import { useState, useEffect } from 'react'
import { healthCheck, getBackendUrl, setBackendUrl } from './api'
import UploadComponent from './components/UploadComponent'
import QueryInput from './components/QueryInput'
import ResultDisplay from './components/ResultDisplay'
import './App.css'

/**
 * App — Main application shell.
 * Layout: Header → Settings → Status → Upload → Query → Results
 */
export default function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [backendStatus, setBackendStatus] = useState('pending')
  const [neo4jStatus, setNeo4jStatus] = useState('pending')
  const [qwenStatus, setQwenStatus] = useState('disconnected')

  // Backend URL settings
  const [backendUrl, setBackendUrlState] = useState(getBackendUrl())
  const [urlInput, setUrlInput] = useState(getBackendUrl())
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Health check function
  const checkHealth = async () => {
    try {
      const data = await healthCheck()
      setBackendStatus('connected')
      if (data.neo4j_uri) setNeo4jStatus('connected')
      if (data.qwen_configured) setQwenStatus('connected')
      else setQwenStatus('disconnected')
    } catch {
      setBackendStatus('disconnected')
      setNeo4jStatus('disconnected')
    }
  }

  // Check health on mount and when URL changes
  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [backendUrl])

  // Save new URL
  const handleSaveUrl = () => {
    const cleaned = urlInput.trim().replace(/\/+$/, '')
    if (!cleaned) return
    setBackendUrl(cleaned)
    setBackendUrlState(cleaned)
    setBackendStatus('pending')
    // Re-check health immediately
    setTimeout(checkHealth, 100)
  }

  const handleUploadComplete = () => {
    setResult(null)
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="logo-icon">⚛</div>
        <h1>DatasheetIQ</h1>
        <p className="subtitle">
          Upload any semiconductor datasheet — query its exact specifications
          through an AI-powered Knowledge Graph
        </p>
      </header>

      {/* Backend URL Settings */}
      <div className="settings-bar">
        <button
          className="settings-toggle"
          onClick={() => setSettingsOpen(!settingsOpen)}
          id="settings-toggle"
        >
          ⚙️ Backend: <span className={`url-badge ${backendStatus}`}>{backendUrl}</span>
        </button>

        {settingsOpen && (
          <div className="settings-panel animate-fade-in">
            <label htmlFor="backend-url-input">Backend URL (Cloudflare / ngrok)</label>
            <div className="settings-input-row">
              <input
                id="backend-url-input"
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://your-tunnel-url.trycloudflare.com"
                onKeyDown={(e) => e.key === 'Enter' && handleSaveUrl()}
              />
              <button onClick={handleSaveUrl} id="save-url-btn">
                Save & Connect
              </button>
            </div>
            <p className="settings-hint">
              Paste your Cloudflare tunnel URL here. It will be saved in your browser.
            </p>
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div className="status-bar">
        <div>
          <span className={`status-dot ${backendStatus}`} />
          Backend API
        </div>
        <div>
          <span className={`status-dot ${neo4jStatus}`} />
          Neo4j Graph
        </div>
        <div>
          <span className={`status-dot ${qwenStatus}`} />
          Qwen AI {qwenStatus === 'disconnected' && '(optional)'}
        </div>
      </div>

      {/* Upload */}
      <UploadComponent onUploadComplete={handleUploadComplete} />

      {/* Query */}
      <QueryInput onResult={setResult} onLoading={setLoading} />

      {/* Results */}
      <ResultDisplay result={result} />
    </div>
  )
}
