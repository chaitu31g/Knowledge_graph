import { useState, useEffect } from 'react'
import { healthCheck, getBackendUrl, setBackendUrl } from './api'
import UploadComponent from './components/UploadComponent'
import ChatbotComponent from './components/ChatbotComponent'
import DataManagerComponent from './components/DataManagerComponent'
import './App.css'

/**
 * App — Main application shell.
 */
export default function App() {
  const [backendStatus, setBackendStatus] = useState('pending')
  const [neo4jStatus, setNeo4jStatus] = useState('pending')
  const [qwenStatus, setQwenStatus] = useState('disconnected')
  const [dataVersion, setDataVersion] = useState(0)

  const [backendUrl, setBackendUrlState] = useState(getBackendUrl())
  const [urlInput, setUrlInput] = useState(getBackendUrl())
  const [settingsOpen, setSettingsOpen] = useState(false)

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
      setQwenStatus('disconnected')
    }
  }

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [backendUrl])

  const handleSaveUrl = () => {
    const cleaned = urlInput.trim().replace(/\/+$/, '')
    if (!cleaned) return
    setBackendUrl(cleaned)
    setBackendUrlState(cleaned)
    setBackendStatus('pending')
    setTimeout(checkHealth, 100)
  }

  const handleDataChanged = () => setDataVersion(v => v + 1)

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo-icon">⚛</div>
        <h1>DatasheetIQ</h1>
        <p className="subtitle">
          Upload semiconductor datasheets — query specs using AI &amp; Knowledge Graph
        </p>
      </header>

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
                Save &amp; Connect
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="status-bar">
        <div><span className={`status-dot ${backendStatus}`} />Backend API</div>
        <div><span className={`status-dot ${neo4jStatus}`} />Neo4j Graph</div>
        <div><span className={`status-dot ${qwenStatus}`} />Qwen AI {qwenStatus === 'disconnected' && '(offline)'}</div>
      </div>

      <div className="main-layout">
        <div className="upload-sidebar">
          <UploadComponent onUploadComplete={handleDataChanged} />
          <DataManagerComponent key={dataVersion} onDataChanged={handleDataChanged} />
        </div>
        <div className="chat-main">
          <ChatbotComponent key={dataVersion} />
        </div>
      </div>
    </div>
  )
}
