/**
 * ResultDisplay — Renders query results as tables or text.
 * Columns are ALWAYS determined dynamically from the backend data.
 */
export default function ResultDisplay({ result }) {
  if (!result) {
    return (
      <div className="glass-card animate-fade-in-up" style={{ animationDelay: '300ms' }}>
        <div className="empty-state">
          <div className="empty-icon">🧠</div>
          <p>Upload a datasheet and ask a question to see results from the Knowledge Graph</p>
        </div>
      </div>
    )
  }

  const { type, data, source, ai_answer } = result

  return (
    <div className="glass-card result-section animate-fade-in-up" style={{ animationDelay: '150ms' }}>
      <div className="card-header">
        <div className="card-icon">{type === 'table' ? '📊' : '📝'}</div>
        <h2>Results</h2>
      </div>

      {/* Meta bar */}
      <div className="result-meta">
        <span className={`result-type type-${type}`}>
          {type === 'table' ? '◈ Table Result' : '◈ Text Result'}
        </span>
        {source && <span className="result-source">{source}</span>}
      </div>

      {/* AI Answer */}
      {ai_answer && (
        <div className="ai-answer">
          <div className="ai-label">✦ AI Summary</div>
          {ai_answer}
        </div>
      )}

      {/* Table rendering */}
      {type === 'table' && data?.columns && data?.rows ? (
        <TableResult columns={data.columns} rows={data.rows} />
      ) : null}

      {/* Text rendering */}
      {type === 'text' && data ? (
        <TextResult data={data} />
      ) : null}
    </div>
  )
}


/**
 * Dynamic table — columns come from backend, never hardcoded.
 */
function TableResult({ columns, rows }) {
  if (!columns?.length || !rows?.length) {
    return <p className="result-text" style={{ color: 'var(--text-muted)' }}>No data rows returned.</p>
  }

  // Filter out columns that are completely empty
  const nonEmptyCols = columns.filter((col) =>
    rows.some((row) => row[col] !== undefined && row[col] !== null && row[col] !== '')
  )

  return (
    <div className="result-table-wrapper">
      <table className="result-table" id="result-table">
        <thead>
          <tr>
            {nonEmptyCols.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {nonEmptyCols.map((col) => {
                const value = row[col] ?? ''
                const isValue = ['min', 'typ', 'max', 'value'].includes(col.toLowerCase())
                  || /\d/.test(String(value))
                return (
                  <td key={col} className={isValue ? 'value-cell' : ''}>
                    {String(value)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


/**
 * Text result — renders paragraphs, sections, and page references.
 */
function TextResult({ data }) {
  if (data.message) {
    return <p className="result-text">{data.message}</p>
  }

  return (
    <div>
      {data.sections?.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          {data.sections.map((section, idx) => (
            <span key={idx} className="section-tag">{section}</span>
          ))}
        </div>
      )}
      <div className="result-text">{data.content || JSON.stringify(data, null, 2)}</div>
      {data.pages?.length > 0 && (
        <div style={{
          marginTop: '0.75rem',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
        }}>
          Found on page{data.pages.length > 1 ? 's' : ''}: {data.pages.join(', ')}
        </div>
      )}
    </div>
  )
}
