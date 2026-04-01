import { useState, useRef, useCallback } from 'react'
import { uploadPdf } from '../api'

/**
 * UploadComponent — PDF upload with real-time processing steps.
 * Shows exactly what's happening at each stage of the pipeline.
 */
export default function UploadComponent({ onUploadComplete }) {
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [steps, setSteps] = useState([])     // Array of step events
  const [currentStep, setCurrentStep] = useState(null)
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
    setSteps([])
    setCurrentStep(null)
    setError('')
    setResult(null)

    try {
      const finalResult = await uploadPdf(file, (stepData) => {
        setCurrentStep(stepData)

        // Add to steps log (avoid duplicate step numbers for 'processing' → 'done')
        setSteps((prev) => {
          const existing = prev.findIndex(
            (s) => s.step === stepData.step && s.status === 'processing'
          )
          if (stepData.status === 'done' && existing !== -1) {
            // Replace the 'processing' entry with 'done'
            const updated = [...prev]
            updated[existing] = stepData
            return updated
          }
          // For table-level updates, replace previous table update
          if (stepData.step === 4 && stepData.status === 'processing') {
            const lastTableIdx = prev.findLastIndex(
              (s) => s.step === 4 && s.status === 'processing'
            )
            if (lastTableIdx !== -1) {
              const updated = [...prev]
              updated[lastTableIdx] = stepData
              return updated
            }
          }
          return [...prev, stepData]
        })
      })

      setResult(finalResult)
      if (onUploadComplete) onUploadComplete(finalResult)
    } catch (err) {
      const msg = err.message || 'Upload failed'
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

  const getStepIcon = (step) => {
    if (step.status === 'error') return '❌'
    if (step.status === 'complete') return '🎉'
    if (step.status === 'done') return '✅'
    return '⏳'
  }

  const getProgressPercent = () => {
    if (!currentStep) return 0
    if (currentStep.status === 'complete') return 100
    if (currentStep.status === 'error') return 0
    return Math.round((currentStep.step / currentStep.total_steps) * 100)
  }

  return (
    <div className="glass-card animate-fade-in-up" style={{ animationDelay: '100ms' }}>
      <div className="card-header">
        <div className="card-icon">📄</div>
        <h2>Upload Datasheet</h2>
        {result && <span className="card-badge">✓ Ingested</span>}
      </div>

      {/* Drop zone — hide when processing */}
      {!uploading && !result && (
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
            {dragActive ? '📥' : '📋'}
          </div>
          <p>Drop a PDF datasheet here or click to browse</p>
          <p className="upload-hint">Supports any semiconductor datasheet format</p>
        </div>
      )}

      {/* Live Processing Steps */}
      {(uploading || steps.length > 0) && (
        <div className="processing-tracker">
          {/* Overall progress bar */}
          <div className="progress-overall">
            <div className="progress-bar-track">
              <div
                className="progress-bar-fill animated-fill"
                style={{ width: `${getProgressPercent()}%` }}
              />
            </div>
            <span className="progress-percent">{getProgressPercent()}%</span>
          </div>

          {/* Step list */}
          <div className="step-list">
            {steps.map((step, i) => (
              <div
                key={`${step.step}-${step.status}-${i}`}
                className={`step-item ${step.status} animate-step-in`}
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <span className="step-icon">{getStepIcon(step)}</span>
                <div className="step-content">
                  <div className="step-message">{step.message}</div>
                  <div className="step-detail">{step.detail}</div>
                </div>
                {step.status === 'processing' && (
                  <span className="step-spinner" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="upload-status error" style={{ marginTop: '0.75rem' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Final Result Stats */}
      {result && !uploading && (
        <div className="animate-fade-in">
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

          {/* Upload another */}
          <button
            className="upload-another-btn"
            onClick={() => {
              setResult(null)
              setSteps([])
              setCurrentStep(null)
            }}
          >
            📄 Upload another datasheet
          </button>
        </div>
      )}
    </div>
  )
}
