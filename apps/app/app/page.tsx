"use client";
import React, { useState } from 'react';
import Aurora from '@/components/Aurora';
import SplitText from '@/components/SplitText';

type AnalysisSection = {
  title: string;
  content: string;
  evidence: string[];
  verified: boolean;
};

type ChatMessage = {
  role: 'user' | 'ai';
  text: string;
  sections?: AnalysisSection[];
};

export default function ChatPage() {
  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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
      if (res.ok && data.doc_id) {
        setDocId(data.doc_id);
        setMessages([{ role: 'ai', text: `${data.filename} is ready. Ask a question about the document to get a plain-language explanation.` }]);
      } else {
        setMessages(prev => [...prev, { role: 'ai', text: data.error || 'I couldn’t upload that document. Please try again.' }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'ai', text: 'I couldn’t connect to the document service. Check that the app is running, then try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input || !docId) return;
    const userMsg: ChatMessage = { role: 'user', text: input };
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
      if (!res.ok) {
        throw new Error(data.detail || data.error || 'The document could not be analyzed.');
      }
      setMessages(prev => [...prev, {
        role: 'ai',
        text: data.response || 'I couldn’t generate an analysis. Please try asking in a different way.',
        sections: Array.isArray(data.sections) ? data.sections : undefined,
      }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'I couldn’t connect to the analysis service.';
      setMessages(prev => [...prev, { role: 'ai', text: message }]);
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
            <div className={`w-full max-w-2xl rounded-xl p-4 ${m.role === 'user' ? 'bg-blue-600 text-white' : 'border border-white/10 bg-slate-900/80 text-slate-100 backdrop-blur-sm'}`}>
              {m.role === 'ai' && m.sections?.length ? (
                <div className="space-y-4">
                  <p className="text-sm leading-6 text-slate-300">
                    I’ve grouped the review into sections. Expand the related document text to compare it with each explanation.
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {m.sections.map((section) => (
                      <section key={section.title} className="rounded-lg border border-white/10 bg-slate-950/60 p-4">
                        <h2 className="mb-2 text-sm font-semibold text-cyan-200">{section.title}</h2>
                        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-100">{section.content}</p>
                        {section.evidence.length > 0 && (
                          <details className="mt-3 border-t border-white/10 pt-2">
                            <summary className="cursor-pointer text-xs font-medium text-slate-400 hover:text-slate-200">
                              View related document text
                            </summary>
                            <ul className="mt-2 space-y-2">
                              {section.evidence.map((quote, quoteIndex) => (
                                <li key={quoteIndex} className="border-l-2 border-cyan-500/60 pl-3 text-xs leading-5 text-slate-300">
                                  “{quote}”
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                        {!section.verified && (
                          <p className="mt-2 text-xs text-amber-300">I couldn’t find matching document text to check this section.</p>
                        )}
                      </section>
                    ))}
                  </div>
                  <p className="text-xs text-slate-400">For information only; this is not legal advice.</p>
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-6">{m.text}</p>
              )}
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
