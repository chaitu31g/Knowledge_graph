import { useState, useRef, useEffect } from 'react'
import { queryDatasheet, getComponents } from '../api'

/**
 * ChatbotComponent — Replaces the static query input with a conversation thread.
 * Qwen 3.5 4B acts as the primary speaker, backed by Knowledge Graph data.
 */
export default function ChatbotComponent() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm your Datasheet assistant. Upload a datasheet, and I'll help you find exact specs from the Knowledge Graph. What would you like to know?",
      type: 'text'
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [component, setComponent] = useState('')
  const [components, setComponents] = useState([])
  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Fetch components for the filter
  useEffect(() => {
    const fetchComponents = async () => {
      try {
        const list = await getComponents()
        setComponents(list)
      } catch (e) {
        console.error("Failed to fetch components", e)
      }
    }
    fetchComponents()
  }, [])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userQuery = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userQuery }])
    setLoading(true)

    try {
      const response = await queryDatasheet(userQuery, component)
      const rows = Array.isArray(response.data) ? response.data : []
      const content = rows.length > 0
        ? `Found ${rows.length} matching parameter row${rows.length === 1 ? '' : 's'}.`
        : 'No matching parameter rows found.'
      
      const aiMsg = {
        role: 'assistant',
        content,
        data: response.data,
        type: response.type,
        source: response.source
      }
      
      setMessages(prev => [...prev, aiMsg])
    } catch (err) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Sorry, I encountered an error connecting to the Knowledge Graph.",
        type: 'error'
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass-card chatbot-container animate-fade-in-up">
      <div className="card-header chatbot-header">
        <div className="ai-status">
          <div className="ai-avatar">🤖</div>
          <div>
            <div className="ai-name">DatasheetIQ AI</div>
            <div className="ai-subtitle">Powered by Qwen 3.5 4B & Neo4j</div>
          </div>
        </div>
        
        {components.length > 0 && (
          <select 
            className="chat-component-select"
            value={component}
            onChange={(e) => setComponent(e.target.value)}
          >
            <option value="">All Components</option>
            {components.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message-bubble-wrapper ${msg.role}`}>
            <div className={`message-bubble ${msg.role}`}>
              <div className="message-content">
                {msg.content.split('\n').map((line, j) => (
                  <p key={j}>{line || '\u00A0'}</p>
                ))}
              </div>
              
              {/* Show source data if present */}
              {msg.data && msg.type === 'table' && Array.isArray(msg.data) && msg.data.length > 0 && (
                <CollapsibleTable rows={msg.data} />
              )}

              {msg.source && <div className="message-source">Source: {msg.source}</div>}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message-bubble-wrapper assistant">
            <div className="message-bubble assistant typing">
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-area" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="Ask a question about the datasheet..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? '...' : 'Send'}
        </button>
      </form>
    </div>
  )
}

/**
 * Collapsible table for source data within a chat bubble
 */
function CollapsibleTable({ rows }) {
  const [isOpen, setIsOpen] = useState(false)
  const columns = ['parameter', 'value', 'unit', 'condition']
  const nonEmptyCols = columns.filter((col) =>
    rows.some((row) => row[col] !== undefined && row[col] !== null && row[col] !== '')
  )

  return (
    <div className="collapsible-source">
      <button className="toggle-source-btn" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? 'Close Source Table' : '📊 Click to see Source Table'}
      </button>
      
      {isOpen && (
        <div className="inner-table-wrapper animate-fade-in">
          <table className="mini-result-table">
            <thead>
              <tr>{nonEmptyCols.map(col => <th key={col}>{col}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {nonEmptyCols.map(col => <td key={col}>{String(row[col] ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
