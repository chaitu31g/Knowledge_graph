/**
 * API helper — centralized HTTP client with dynamic backend URL.
 *
 * The base URL is stored in localStorage so it persists across reloads.
 * Users can change it anytime from the settings panel when the
 * Cloudflare tunnel URL rotates.
 */
import axios from 'axios'

const STORAGE_KEY = 'datasheetiq_backend_url'
const DEFAULT_URL = 'http://localhost:8000'

/**
 * Get the currently configured backend URL.
 */
export function getBackendUrl() {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_URL
}

/**
 * Save a new backend URL.
 */
export function setBackendUrl(url) {
  const cleaned = url.replace(/\/+$/, '')
  localStorage.setItem(STORAGE_KEY, cleaned)
}

/**
 * Create an axios instance pointing to the current backend URL.
 */
function getClient() {
  return axios.create({
    baseURL: getBackendUrl(),
    timeout: 120000,
  })
}

// ── API functions ────────────────────────────────────────────

export async function healthCheck() {
  const res = await getClient().get('/health')
  return res.data
}

/**
 * Upload a PDF with real-time SSE progress updates.
 * @param {File} file - The PDF file to upload
 * @param {Function} onStep - Callback called with each progress step object
 * @returns {Promise<Object>} - The final upload result
 */
export async function uploadPdf(file, onStep) {
  const formData = new FormData()
  formData.append('file', file)

  const baseUrl = getBackendUrl()

  const response = await fetch(`${baseUrl}/api/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `Upload failed with status ${response.status}`)
  }

  // Read SSE stream
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Parse SSE events from buffer
    const lines = buffer.split('\n')
    buffer = lines.pop() || '' // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (onStep) onStep(data)
          if (data.status === 'complete' && data.result) {
            finalResult = data.result
          }
          if (data.status === 'error') {
            throw new Error(data.message)
          }
        } catch (e) {
          if (e.message && !e.message.startsWith('Unexpected')) throw e
        }
      }
    }
  }

  return finalResult
}

export async function queryDatasheet(query, component = '') {
  const res = await getClient().post('/api/query', { query, component })
  return res.data
}

export async function getComponents() {
  const res = await getClient().get('/api/components')
  return res.data.components || []
}
