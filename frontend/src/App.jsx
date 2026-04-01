import { useState, useEffect } from 'react'
import axios from 'axios'
import UploadComponent from './components/UploadComponent'
import QueryInput from './components/QueryInput'
import ResultDisplay from './components/ResultDisplay'
import './App.css'

/**
 * App — Main application shell.
 * Layout: Header → Status → Upload → Query → Results
 */
export default function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [backendStatus, setBackendStatus] = useState('pending')
  const [neo4jStatus, setNeo4jStatus] = useState('pending')
  const [qwenStatus, setQwenStatus] = useState('disconnected')

  // Check backend health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await axios.get('/health')
        setBackendStatus('connected')
        // Infer Neo4j and Qwen status from health response
        if (res.data.neo4j_uri) setNeo4jStatus('connected')
        if (res.data.qwen_configured) setQwenStatus('connected')
        else setQwenStatus('disconnected')
      } catch {
        setBackendStatus('disconnected')
        setNeo4jStatus('disconnected')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleUploadComplete = (data) => {
    // Refresh component list after upload
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
