import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  Send,
  Upload,
  Cpu,
  Database,
  MessageSquare,
  Loader2,
  Zap,
  AlertCircle,
  WifiOff,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Connection status constants
const STATUS = {
  IDLE: 'IDLE',
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  ERROR: 'ERROR',
};

const App = () => {
  const [backendUrl, setBackendUrl] = useState(localStorage.getItem('backendUrl') || '');
  const [connectionStatus, setConnectionStatus] = useState(STATUS.IDLE);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [specs, setSpecs] = useState({ Vgs: 'N/A', Id: 'N/A', Rdson: 'N/A' });
  const [dragActive, setDragActive] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Validate and clean the backend URL
  const getCleanUrl = (url) => {
    const trimmed = url.trim();
    return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed;
  };

  const handleConnect = async () => {
    const cleanUrl = getCleanUrl(backendUrl);
    if (!cleanUrl) return;

    setConnectionStatus(STATUS.CONNECTING);
    try {
      const res = await axios.get(`${cleanUrl}/health`, { timeout: 10000 });
      if (res.status === 200) {
        setConnectionStatus(STATUS.CONNECTED);
        setBackendUrl(cleanUrl);
        localStorage.setItem('backendUrl', cleanUrl);
      }
    } catch (err) {
      setConnectionStatus(STATUS.ERROR);
    }
  };

  const handleFileUpload = async (file) => {
    if (connectionStatus !== STATUS.CONNECTED) {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Please connect to the Cloudflare backend first.' }]);
      return;
    }
    setIsProcessing(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${backendUrl}/process`, formData, {
        timeout: 120000, // 2 min — model inference can be slow
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.status === 'success') {
        setMessages(prev => [...prev, { role: 'assistant', content: '✅ **PDF processed via Cloudflare Tunnel.** You can now ask questions about the datasheet.' }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Backend returned an unexpected response. Check Colab logs.' }]);
      }
    } catch (err) {
      const errMsg = err.code === 'ECONNABORTED'
        ? '❌ Request timed out. The model may still be loading on Colab.'
        : '❌ Error processing PDF. Check the Cloudflare backend logs.';
      setMessages(prev => [...prev, { role: 'assistant', content: errMsg }]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    if (connectionStatus !== STATUS.CONNECTED) {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Please connect to the Cloudflare backend before sending a query.' }]);
      return;
    }

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsProcessing(true);

    try {
      const res = await axios.post(`${backendUrl}/chat`, { query: userMsg }, { timeout: 60000 });
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }]);
      if (res.data.specs) setSpecs(res.data.specs);
    } catch (err) {
      const errMsg = err.code === 'ECONNABORTED'
        ? '❌ Request timed out. The GPU may be busy.'
        : '❌ Connection error to Cloudflare GPU.';
      setMessages(prev => [...prev, { role: 'assistant', content: errMsg }]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Status indicator config
  const statusConfig = {
    [STATUS.IDLE]:       { dot: 'bg-slate-500',                     label: 'Ready to Connect' },
    [STATUS.CONNECTING]: { dot: 'bg-amber-500 animate-pulse',        label: 'Connecting...' },
    [STATUS.CONNECTED]:  { dot: 'bg-emerald-500 shadow-[0_0_8px_#10b981]', label: 'Cloudflare Tunnel Active' },
    [STATUS.ERROR]:      { dot: 'bg-rose-500',                       label: 'Connection Failed' },
  };
  const { dot, label } = statusConfig[connectionStatus];

  return (
    <div className="flex h-screen bg-[#020617] text-slate-100 font-sans overflow-hidden">

      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className="w-80 bg-[#0f172a] border-r border-slate-800 flex flex-col p-6 space-y-8 shrink-0">

        {/* Logo */}
        <div className="flex items-center space-x-3 text-sky-400">
          <Cpu size={28} />
          <h1 className="text-2xl font-bold tracking-tight">CircuitAI</h1>
        </div>

        {/* Connection Panel */}
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
              title="Connect to backend"
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

        {/* Spec Summary Panel */}
        <section className="flex-1 space-y-3 pt-4 border-t border-slate-800 overflow-y-auto">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Component Analysis</h2>
          <div className="grid grid-cols-1 gap-3">
            <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50 hover:border-sky-500/30 transition-all">
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">Gate Threshold</div>
              <div className="text-xs text-slate-500 font-mono mb-1">V_GS(th)</div>
              <div className="text-xl font-mono text-sky-400">{specs.Vgs}</div>
            </div>
            <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50 hover:border-sky-500/30 transition-all">
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">Drain Current (Max)</div>
              <div className="text-xs text-slate-500 font-mono mb-1">I_D</div>
              <div className="text-xl font-mono text-emerald-400">{specs.Id}</div>
            </div>
            <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50 hover:border-sky-500/30 transition-all">
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">On-State Resistance</div>
              <div className="text-xs text-slate-500 font-mono mb-1">R_DS(on)</div>
              <div className="text-xl font-mono text-orange-400">{specs.Rdson}</div>
            </div>
          </div>
        </section>
      </aside>

      {/* ── Main Chat Area ───────────────────────────────────────── */}
      <main className="flex-1 flex flex-col relative min-w-0">

        {/* Disconnected Banner */}
        {connectionStatus !== STATUS.CONNECTED && (
          <div className="flex items-center justify-center space-x-2 bg-rose-500/10 border-b border-rose-500/20 text-rose-400 text-[10px] py-1.5 uppercase tracking-widest z-10">
            <WifiOff size={10} />
            <span>Cloudflare backend not connected — paste your URL in the sidebar</span>
          </div>
        )}

        {/* Message Area */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-8 space-y-6 scroll-smooth"
        >
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center space-y-4 opacity-30 select-none">
              <MessageSquare size={56} className="text-slate-600" />
              <div className="text-center">
                <p className="text-base font-medium text-slate-400">No datasheet analyzed yet</p>
                <p className="text-sm text-slate-500 mt-1">Connect to Cloudflare and upload a PDF to begin</p>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  'flex space-x-3 max-w-3xl animate-in',
                  msg.role === 'user' ? 'ml-auto flex-row-reverse space-x-reverse' : ''
                )}
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
            ))
          )}

          {/* Thinking indicator */}
          {isProcessing && (
            <div className="flex space-x-3 animate-pulse">
              <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center">
                <Loader2 size={14} className="animate-spin text-sky-400" />
              </div>
              <div className="flex items-center space-x-1.5 bg-[#1e293b] border border-slate-700/60 px-4 rounded-2xl rounded-tl-sm h-10">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-6 border-t border-slate-800 flex flex-col space-y-3 bg-[#020617]">

          {/* PDF Drop Zone */}
          <div
            className={cn(
              'border-2 border-dashed rounded-xl py-3 px-4 transition-all flex items-center justify-center space-x-3 cursor-pointer',
              dragActive ? 'border-sky-500 bg-sky-500/5' : 'border-slate-800 hover:border-slate-700',
              isProcessing ? 'opacity-50 pointer-events-none' : ''
            )}
            onDragOver={e => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={e => {
              e.preventDefault();
              setDragActive(false);
              const file = e.dataTransfer.files[0];
              if (file && file.type === 'application/pdf') handleFileUpload(file);
            }}
            onClick={() => document.getElementById('pdf-file-input')?.click()}
          >
            <Upload size={16} className="text-slate-500 shrink-0" />
            <p className="text-xs text-slate-500 font-medium">
              {isProcessing ? 'Processing on Colab GPU...' : 'Drop PDF datasheet here, or click to browse'}
            </p>
            <input
              id="pdf-file-input"
              type="file"
              className="hidden"
              accept=".pdf"
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
                // Reset so same file can be re-uploaded
                e.target.value = '';
              }}
            />
          </div>

          {/* Chat Input */}
          <div className="relative">
            <input
              type="text"
              placeholder="Ask about V_GS, I_D, schematic blocks, or any spec..."
              className="w-full bg-[#1e293b] border border-slate-700 rounded-xl py-3.5 pl-5 pr-14 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500/50 transition-all placeholder-slate-600"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
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

          {/* Status Footer */}
          <div className="flex justify-between items-center px-1">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-1.5 text-[10px] text-slate-600 font-mono">
                <Database size={10} />
                <span>CHROMA_DB</span>
              </div>
              <div className="flex items-center space-x-1.5 text-[10px] text-slate-600 font-mono">
                <Zap size={10} className="text-amber-600" />
                <span>FLASHRANK RERANKER</span>
              </div>
              <div className="flex items-center space-x-1.5 text-[10px] text-slate-600 font-mono">
                <Cpu size={10} />
                <span>QWEN2.5-VL 3B-INT4</span>
              </div>
            </div>
            <p className="text-[10px] text-slate-700 uppercase tracking-widest font-semibold">T4/L4 GPU</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
