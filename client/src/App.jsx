import React, { useState, useRef, useEffect } from 'react';
import {
  Send, Upload, Cpu, Database, MessageSquare,
  Loader2, Zap, WifiOff, Terminal,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

// Simple class merge util — no external dep needed
const cn = (...classes) => classes.filter(Boolean).join(' ');

const STATUS = { IDLE: 'IDLE', CONNECTING: 'CONNECTING', CONNECTED: 'CONNECTED', ERROR: 'ERROR' };

// ── Terminal Log Box ───────────────────────────────────────────
// Renders accumulated processing logs in a dark terminal style.
const TerminalBox = ({ logs, isActive }) => {
  const termRef = useRef(null);

  useEffect(() => {
    if (termRef.current) {
      termRef.current.scrollTop = termRef.current.scrollHeight;
    }
  }, [logs]);

  const typeStyle = (type) => {
    switch (type) {
      case 'done':    return 'text-emerald-400';
      case 'error':   return 'text-rose-400';
      case 'header':  return 'text-sky-400 font-bold';
      case 'page':    return 'text-violet-300';
      default:        return 'text-slate-300';
    }
  };

  return (
    <div className="w-full rounded-xl overflow-hidden border border-slate-700 shadow-2xl">
      {/* Terminal title bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1.5">
            <div className="w-3 h-3 rounded-full bg-rose-500/80" />
            <div className="w-3 h-3 rounded-full bg-amber-500/80" />
            <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
          </div>
          <div className="flex items-center space-x-1.5 ml-2">
            <Terminal size={11} className="text-slate-400" />
            <span className="text-[11px] text-slate-400 font-mono">circuitai — pipeline</span>
          </div>
        </div>
        {isActive && (
          <div className="flex items-center space-x-1.5">
            <Loader2 size={11} className="animate-spin text-sky-400" />
            <span className="text-[10px] text-sky-400 font-mono">running</span>
          </div>
        )}
      </div>

      {/* Log output area */}
      <div
        ref={termRef}
        className="bg-[#0d1117] px-4 py-3 font-mono text-[12px] leading-relaxed overflow-y-auto"
        style={{ maxHeight: '280px', minHeight: '120px' }}
      >
        {logs.map((log, i) => (
          <div key={i} className="flex space-x-2 mb-0.5">
            <span className="text-slate-600 shrink-0 select-none">{log.ts}</span>
            <span className={typeStyle(log.type)}>{log.text}</span>
          </div>
        ))}
        {isActive && (
          <div className="flex space-x-2 mt-1">
            <span className="text-slate-600 select-none">      </span>
            <span className="text-slate-400 animate-pulse">█</span>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Main App ──────────────────────────────────────────────────
const App = () => {
  const [backendUrl, setBackendUrl]           = useState(localStorage.getItem('backendUrl') || '');
  const [connectionStatus, setConnectionStatus] = useState(STATUS.IDLE);
  const [messages, setMessages]               = useState([]);
  const [input, setInput]                     = useState('');
  const [isProcessing, setIsProcessing]       = useState(false);
  const [specs, setSpecs]                     = useState({ Vgs: 'N/A', Id: 'N/A', Rdson: 'N/A' });
  const [dragActive, setDragActive]           = useState(false);
  // Terminal log state — array of { ts, text, type }
  const [termLogs, setTermLogs]               = useState([]);
  const [termActive, setTermActive]           = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, termLogs]);

  const getCleanUrl = (url) => url.trim().replace(/\/$/, '');

  const now = () => {
    const d = new Date();
    return `[${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}]`;
  };

  const addLog = (text, type = 'info') => {
    setTermLogs(prev => [...prev, { ts: now(), text, type }]);
  };

  const handleConnect = async () => {
    const cleanUrl = getCleanUrl(backendUrl);
    if (!cleanUrl) return;
    setConnectionStatus(STATUS.CONNECTING);
    try {
      const res = await fetch(`${cleanUrl}/health`, { signal: AbortSignal.timeout(10000) });
      if (res.ok) {
        setConnectionStatus(STATUS.CONNECTED);
        setBackendUrl(cleanUrl);
        localStorage.setItem('backendUrl', cleanUrl);
      } else {
        setConnectionStatus(STATUS.ERROR);
      }
    } catch {
      setConnectionStatus(STATUS.ERROR);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    if (connectionStatus !== STATUS.CONNECTED) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Please connect to the Cloudflare backend first.',
      }]);
      return;
    }

    // Reset and open terminal
    setTermLogs([]);
    setTermActive(true);
    setIsProcessing(true);
    addLog(`Uploading ${file.name} (${(file.size / 1024).toFixed(1)} KB)...`, 'header');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${backendUrl}/process`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status} — ${text}`);
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            const { type, message, page, total, specs: newSpecs } = data;

            if (type === 'progress') {
              const logType = (data.step === 'extract' && page) ? 'page' : 'info';
              addLog(message, logType);

            } else if (type === 'done') {
              addLog(message, 'done');
              setTermActive(false);
              if (newSpecs) setSpecs(newSpecs);
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: `✅ **${message}**\n\nYou can now ask questions about the datasheet.`,
              }]);

            } else if (type === 'error') {
              addLog(`ERROR: ${message}`, 'error');
              setTermActive(false);
            }
          } catch {
            // skip malformed SSE line
          }
        }
      }
    } catch (err) {
      addLog(`FATAL: ${err.message}`, 'error');
      setTermActive(false);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `❌ Upload failed: ${err.message}`,
      }]);
    } finally {
      setIsProcessing(false);
      setTermActive(false);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isProcessing) return;
    if (connectionStatus !== STATUS.CONNECTED) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Please connect to the backend first.',
      }]);
      return;
    }

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsProcessing(true);

    try {
      const res = await fetch(`${backendUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg }),
        signal: AbortSignal.timeout(60000),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      if (data.specs) setSpecs(data.specs);
    } catch (err) {
      const msg = err.name === 'TimeoutError'
        ? '❌ Request timed out. The GPU may be busy.'
        : `❌ ${err.message}`;
      setMessages(prev => [...prev, { role: 'assistant', content: msg }]);
    } finally {
      setIsProcessing(false);
    }
  };

  const statusConfig = {
    [STATUS.IDLE]:       { dot: 'bg-slate-500',     label: 'Ready to Connect' },
    [STATUS.CONNECTING]: { dot: 'bg-amber-500 animate-pulse', label: 'Connecting...' },
    [STATUS.CONNECTED]:  { dot: 'bg-emerald-500', label: 'Cloudflare Tunnel Active' },
    [STATUS.ERROR]:      { dot: 'bg-rose-500',       label: 'Connection Failed' },
  };
  const { dot, label } = statusConfig[connectionStatus];

  const showTerminal = termLogs.length > 0;

  return (
    <div className="flex h-screen bg-[#020617] text-slate-100 overflow-hidden" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>

      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className="w-80 bg-[#0f172a] border-r border-slate-800 flex flex-col p-6 space-y-8 shrink-0">
        <div className="flex items-center space-x-3 text-sky-400">
          <Cpu size={28} />
          <h1 className="text-2xl font-bold tracking-tight">CircuitAI</h1>
        </div>

        {/* Connection */}
        <section className="space-y-3">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Connection</h2>
          <div className="relative">
            <input
              type="text"
              placeholder="https://xxxx.trycloudflare.com"
              className="w-full bg-[#1e293b] border border-slate-700 rounded-lg py-2 pl-3 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/50 text-slate-200 placeholder-slate-600"
              value={backendUrl}
              onChange={e => setBackendUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleConnect()}
            />
            <button
              onClick={handleConnect}
              disabled={connectionStatus === STATUS.CONNECTING}
              className="absolute right-1 top-1/2 -translate-y-1/2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 transition-colors p-1.5 rounded-md"
            >
              <Zap size={14} />
            </button>
          </div>
          <div className="flex items-center space-x-2 text-xs">
            <div className={cn('w-2 h-2 rounded-full shrink-0', dot)} />
            <span className="text-slate-400">{label}</span>
          </div>
        </section>

        {/* Spec cards */}
        <section className="flex-1 space-y-3 pt-4 border-t border-slate-800 overflow-y-auto">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Component Analysis</h2>
          <div className="grid grid-cols-1 gap-3">
            {[
              { label: 'Gate Threshold',      sub: 'V_GS(th)', value: specs.Vgs,   color: 'text-sky-400' },
              { label: 'Drain Current (Max)', sub: 'I_D',      value: specs.Id,    color: 'text-emerald-400' },
              { label: 'On-State Resistance', sub: 'R_DS(on)', value: specs.Rdson, color: 'text-orange-400' },
            ].map(({ label, sub, value, color }) => (
              <div key={sub} className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50 hover:border-sky-500/30 transition-all">
                <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">{label}</div>
                <div className="text-xs text-slate-500 font-mono mb-1">{sub}</div>
                <div className={cn('text-xl font-mono', color)}>{value}</div>
              </div>
            ))}
          </div>
        </section>
      </aside>

      {/* ── Main chat area ───────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Connection warning banner */}
        {connectionStatus !== STATUS.CONNECTED && (
          <div className="flex items-center justify-center space-x-2 bg-rose-500/10 border-b border-rose-500/20 text-rose-400 text-[10px] py-1.5 uppercase tracking-widest">
            <WifiOff size={10} />
            <span>Cloudflare backend not connected — paste your URL in the sidebar</span>
          </div>
        )}

        {/* Messages + terminal */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-5">

          {/* Empty state */}
          {messages.length === 0 && !showTerminal && (
            <div className="h-full flex flex-col items-center justify-center space-y-4 opacity-30 select-none">
              <MessageSquare size={56} className="text-slate-600" />
              <div className="text-center">
                <p className="text-base font-medium text-slate-400">No datasheet analyzed yet</p>
                <p className="text-sm text-slate-500 mt-1">Connect to Cloudflare and upload a PDF to begin</p>
              </div>
            </div>
          )}

          {/* Chat messages */}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn('flex space-x-3 max-w-3xl', msg.role === 'user' ? 'ml-auto flex-row-reverse space-x-reverse' : '')}
            >
              <div className={cn(
                'w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold',
                msg.role === 'user' ? 'bg-sky-600 text-white' : 'bg-slate-800 text-sky-400'
              )}>
                {msg.role === 'user' ? 'U' : <Cpu size={14} />}
              </div>
              <div className={cn(
                'p-4 rounded-2xl text-sm leading-relaxed max-w-full',
                msg.role === 'user'
                  ? 'bg-sky-600 text-white rounded-tr-sm'
                  : 'bg-[#1e293b] border border-slate-700/60 shadow-lg rounded-tl-sm'
              )}>
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  className="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-900 prose-code:text-sky-400"
                >
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          ))}

          {/* ── Terminal progress box ── */}
          {showTerminal && (
            <TerminalBox logs={termLogs} isActive={termActive} />
          )}

          {/* Chat thinking dots */}
          {isProcessing && !showTerminal && (
            <div className="flex space-x-3">
              <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center">
                <Loader2 size={14} className="animate-spin text-sky-400" />
              </div>
              <div className="flex items-center space-x-1.5 bg-[#1e293b] border border-slate-700/60 px-4 rounded-2xl rounded-tl-sm h-10">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
        </div>

        {/* ── Input bar ─────────────────────────────────────────── */}
        <div className="p-5 border-t border-slate-800 space-y-3 bg-[#020617]">

          {/* Drop zone */}
          <div
            className={cn(
              'border-2 border-dashed rounded-xl py-3 px-4 flex items-center justify-center space-x-3 cursor-pointer transition-all',
              dragActive    ? 'border-sky-500 bg-sky-500/5 text-sky-300' : 'border-slate-800 hover:border-slate-600 text-slate-500',
              isProcessing  ? 'opacity-40 pointer-events-none' : ''
            )}
            onDragOver={e => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={e => {
              e.preventDefault(); setDragActive(false);
              const file = e.dataTransfer.files?.[0];
              if (file?.type === 'application/pdf') handleFileUpload(file);
            }}
            onClick={() => !isProcessing && document.getElementById('pdf-file-input')?.click()}
          >
            <Upload size={15} className="shrink-0" />
            <p className="text-xs font-medium">
              {isProcessing
                ? '⚙️ Processing — see terminal above...'
                : 'Drop PDF datasheet here, or click to browse'}
            </p>
            <input
              id="pdf-file-input"
              type="file"
              className="hidden"
              accept=".pdf"
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
                e.target.value = '';
              }}
            />
          </div>

          {/* Chat input */}
          <div className="relative">
            <input
              type="text"
              placeholder="Ask about V_GS, I_D, schematic blocks, or any spec..."
              className="w-full bg-[#1e293b] border border-slate-700 rounded-xl py-3.5 pl-5 pr-14 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/30 placeholder-slate-600 transition-all"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
              disabled={isProcessing}
            />
            <button
              onClick={handleSendMessage}
              disabled={!input.trim() || isProcessing}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-500 transition-all rounded-lg text-white"
            >
              <Send size={16} />
            </button>
          </div>

          {/* Footer chips */}
          <div className="flex justify-between items-center px-1">
            <div className="flex items-center space-x-4">
              {[
                { icon: <Database size={10} />, label: 'CHROMA_DB' },
                { icon: <Zap size={10} className="text-amber-600" />, label: 'FLASHRANK' },
                { icon: <Cpu size={10} />, label: 'QWEN2.5-VL 3B-INT4' },
              ].map(({ icon, label }) => (
                <div key={label} className="flex items-center space-x-1.5 text-[10px] text-slate-600 font-mono">
                  {icon}<span>{label}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-700 uppercase tracking-widest font-semibold">T4/L4 GPU</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
