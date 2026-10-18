"use client";
import React, { useState } from 'react';
import Aurora from '@/components/Aurora';
import SplitText from '@/components/SplitText';

export default function ChatPage() {
  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [messages, setMessages] = useState<{role: string, text: string}[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://127.0.0.1:8000/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.doc_id) {
        setDocId(data.doc_id);
        setMessages([{ role: 'ai', text: `Document ${data.filename} uploaded. How can I help you analyze it?` }]);
      } else {
        alert(data.error || 'Upload failed');
      }
    } catch (e) {
      alert('Error uploading file');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input || !docId) return;
    const userMsg = { role: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const formData = new FormData();
    formData.append('doc_id', docId);
    formData.append('query', input);

    try {
      const res = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'ai', text: data.response }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'ai', text: 'Error connecting to backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative isolate flex h-screen flex-col overflow-hidden bg-slate-950 font-sans text-white">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-0">
        <Aurora
          colorStops={['#6769ff', '#22d3c5', '#8f5cff']}
          amplitude={1.4}
          blend={0.5}
          speed={0.6}
          glow={1.2}
          layers={3}
          direction="top"
        />
      </div>
      <header className="relative z-10 flex items-center justify-between border-b border-white/10 bg-slate-950/35 p-4 backdrop-blur-sm">
        <h1 className="text-xl font-bold text-white">
          <SplitText
            text="ZeroDay PS2 Legal Triage"
            className="inline-block"
            tag="span"
            textAlign="left"
            trigger="load"
            splitType="chars"
            delay={35}
            duration={0.8}
          />
        </h1>
        <div className="flex gap-2">
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="text-sm" />
          <button
            onClick={handleUpload}
            disabled={!file || loading}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
          >
            {loading ? '...' : 'Upload'}
          </button>
        </div>
      </header>

      <main className="relative z-10 flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl rounded-lg p-3 ${m.role === 'user' ? 'bg-blue-600 text-white' : 'border border-white/10 bg-slate-900/70 text-slate-100 backdrop-blur-sm'}`}>
              {m.text}
            </div>
          </div>
        ))}
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-slate-950/45 p-4 backdrop-blur-sm">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={docId ? "Ask a question about the document..." : "Upload a document first"}
            disabled={!docId || loading}
            className="flex-1 rounded border border-white/15 bg-slate-900/80 p-2 text-white outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={!docId || loading}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
          >
            Send
          </button>
        </div>
      </footer>
    </div>
  );
}
