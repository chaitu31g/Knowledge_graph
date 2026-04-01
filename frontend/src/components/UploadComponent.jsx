import { useState, useRef, useCallback } from 'react'
import axios from 'axios'

/**
 * UploadComponent — PDF drag-and-drop upload with progress and stats.
 */
export default function UploadComponent({ onUploadComplete }) {
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const uploadFile = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file')
      return
    }

    setUploading(true)
    setProgress(0)
    setError('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          const pct = Math.round((e.loaded * 100) / (e.total || 1))
          setProgress(pct)
        },
      })

      setResult(response.data)
      if (onUploadComplete) onUploadComplete(response.data)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed'
      setError(msg)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadFile(e.dataTransfer.files[0])
    }
  }, [])

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      uploadFile(e.target.files[0])
    }
  }

  return (
    <div className="glass-card animate-fade-in-up" style={{ animationDelay: '100ms' }}>
      <div className="card-header">
        <div className="card-icon">📄</div>
        <h2>Upload Datasheet</h2>
        {result && <span className="card-badge">✓ Ingested</span>}
      </div>

      <div
        id="upload-zone"
        className={`upload-zone ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleChange}
          id="pdf-upload-input"
        />
        <div className="upload-icon">
          {uploading ? '⏳' : dragActive ? '📥' : '📋'}
        </div>
        <p>
          {uploading
            ? 'Processing datasheet…'
            : 'Drop a PDF datasheet here or click to browse'}
        </p>
        <p className="upload-hint">Supports any semiconductor datasheet format</p>
      </div>

      {/* Progress */}
      {uploading && (
        <div className="upload-progress">
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="upload-status">
            <span className="spinner" style={{
              width: 12, height: 12,
              border: '2px solid rgba(255,255,255,0.2)',
              borderTopColor: 'var(--accent-blue)',
              borderRadius: '50%',
              animation: 'spin 0.6s linear infinite',
              display: 'inline-block',
            }} />
            Parsing PDF &amp; building knowledge graph… {progress}%
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="upload-status error" style={{ marginTop: '0.75rem' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Success stats */}
      {result && !uploading && (
        <div className="animate-fade-in">
          <div className="upload-status success" style={{ marginTop: '0.75rem' }}>
            ✓ {result.message}
          </div>
          <div className="upload-stats stagger">
            <div className="stat-item animate-fade-in-up">
              <div className="stat-value">{result.total_pages}</div>
              <div className="stat-label">Pages</div>
            </div>
            <div className="stat-item animate-fade-in-up">
              <div className="stat-value">{result.tables_found}</div>
              <div className="stat-label">Tables</div>
            </div>
            <div className="stat-item animate-fade-in-up">
              <div className="stat-value">{result.parameters_stored}</div>
              <div className="stat-label">Parameters</div>
            </div>
            <div className="stat-item animate-fade-in-up">
              <div className="stat-value">{result.text_blocks_stored}</div>
              <div className="stat-label">Text Blocks</div>
            </div>
            <div className="stat-item animate-fade-in-up">
              <div className="stat-value">{result.images_found}</div>
              <div className="stat-label">Images</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
