import { useState, useEffect, useCallback } from 'react'
import { getComponents, getDebugInfo, deleteComponent, clearAllData } from '../api'

/**
 * DataManagerComponent — Shows stored components and lets you delete them.
 * Also shows ingestion diagnostics (what's actually in Neo4j).
 */
export default function DataManagerComponent({ onDataChanged }) {
  const [components, setComponents] = useState([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState('')   // component name being deleted
  const [clearing, setClearing] = useState(false)
  const [debugData, setDebugData] = useState(null)
  const [debugComp, setDebugComp] = useState('')
  const [debugLoading, setDebugLoading] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [toast, setToast] = useState('')

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3000)
  }

  const fetchComponents = useCallback(async () => {
    setLoading(true)
    try {
      const list = await getComponents()
      setComponents(list)
    } catch (e) {
      console.error('Failed to fetch components', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchComponents()
  }, [fetchComponents])

  const handleDelete = async (name) => {
    setDeleting(name)
    try {
      const res = await deleteComponent(name)
      showToast(`✅ Deleted "${name}" — ${res.nodes_deleted} nodes removed`)
      await fetchComponents()
      if (debugComp === name) setDebugData(null)
      if (onDataChanged) onDataChanged()
    } catch (e) {
      showToast(`❌ Failed to delete "${name}"`)
    } finally {
      setDeleting('')
    }
  }

  const handleClearAll = async () => {
    if (!confirmClear) {
      setConfirmClear(true)
      setTimeout(() => setConfirmClear(false), 4000)
      return
    }
    setClearing(true)
    setConfirmClear(false)
    try {
      const res = await clearAllData()
      showToast(`🗑️ Graph cleared — ${res.nodes_deleted} nodes deleted`)
      setComponents([])
      setDebugData(null)
      if (onDataChanged) onDataChanged()
    } catch (e) {
      showToast('❌ Failed to clear graph')
    } finally {
      setClearing(false)
    }
  }

  const handleDebug = async (name) => {
    setDebugComp(name)
    setDebugLoading(true)
    setDebugData(null)
    try {
      const data = await getDebugInfo(name)
      setDebugData(data)
    } catch (e) {
      showToast('❌ Debug fetch failed')
    } finally {
      setDebugLoading(false)
    }
  }

  return (
    <div className="glass-card data-manager animate-fade-in-up" style={{ animationDelay: '200ms' }}>
      {/* Header */}
      <div className="card-header">
        <div className="card-icon">🗄️</div>
        <h2>Data Manager</h2>
        <button
          className="refresh-btn"
          onClick={fetchComponents}
          disabled={loading}
          title="Refresh component list"
        >
          {loading ? '⏳' : '🔄'}
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <div className="dm-toast animate-fade-in">{toast}</div>
      )}

      {/* Component List */}
      {components.length === 0 && !loading ? (
        <div className="dm-empty">
          <div className="dm-empty-icon">📭</div>
          <p>No datasheets ingested yet</p>
          <p className="dm-empty-hint">Upload a PDF to get started</p>
        </div>
      ) : (
        <div className="dm-component-list">
          {components.map((comp) => (
            <div key={comp} className="dm-component-row">
              <div className="dm-comp-name">
                <span className="dm-chip">📦</span>
                {comp}
              </div>
              <div className="dm-actions">
                <button
                  className="dm-btn debug"
                  onClick={() => handleDebug(comp)}
                  disabled={debugLoading && debugComp === comp}
                  title="Inspect stored data"
                >
                  {debugLoading && debugComp === comp ? '⏳' : '🔍'}
                </button>
                <button
                  className="dm-btn delete"
                  onClick={() => handleDelete(comp)}
                  disabled={deleting === comp}
                  title={`Delete ${comp}`}
                >
                  {deleting === comp ? '⏳' : '🗑️'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Debug Panel */}
      {debugData && (
        <div className="dm-debug animate-fade-in">
          <div className="dm-debug-header">
            <span>🔍 Debug: {debugData.component}</span>
            <button className="dm-debug-close" onClick={() => setDebugData(null)}>✕</button>
          </div>
          <div className="dm-debug-stats">
            <div className="dm-stat">
              <span className="dm-stat-val">{debugData.total_parameters_in_graph}</span>
              <span className="dm-stat-label">Parameter nodes</span>
            </div>
            <div className="dm-stat">
              <span className="dm-stat-val">{debugData.value_records?.length ?? 0}</span>
              <span className="dm-stat-label">Value records</span>
            </div>
          </div>

          {debugData.value_records?.length > 0 ? (
            <div className="dm-debug-table-wrap">
              <table className="mini-result-table">
                <thead>
                  <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                    <th>Unit</th>
                    <th>Condition</th>
                  </tr>
                </thead>
                <tbody>
                  {debugData.value_records.slice(0, 20).map((r, i) => (
                    <tr key={i}>
                      <td>{r.parameter}</td>
                      <td>{r.value}</td>
                      <td>{r.unit}</td>
                      <td>{r.condition}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {debugData.value_records.length > 20 && (
                <p className="dm-debug-more">
                  … and {debugData.value_records.length - 20} more rows
                </p>
              )}
            </div>
          ) : (
            <div className="dm-debug-warn">
              ⚠️ No value records found — parameters were stored but values/units are missing.
              Check the ingestion pipeline and re-upload.
            </div>
          )}
        </div>
      )}

      {/* Clear All */}
      {components.length > 0 && (
        <div className="dm-footer">
          <button
            className={`clear-all-btn ${confirmClear ? 'confirm' : ''}`}
            onClick={handleClearAll}
            disabled={clearing}
          >
            {clearing
              ? '⏳ Clearing...'
              : confirmClear
              ? '⚠️ Click again to confirm clear all'
              : '🗑️ Clear all data'}
          </button>
        </div>
      )}
    </div>
  )
}
