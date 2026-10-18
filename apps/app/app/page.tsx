"use client";
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PanelLeftOpen, SquarePen } from 'lucide-react';
import Aurora from '@/components/Aurora';
import Sidebar from '@/components/chat/Sidebar';
import Welcome from '@/components/chat/Welcome';
import Composer from '@/components/chat/Composer';
import MessageBubble, { TypingIndicator } from '@/components/chat/MessageBubble';
import {
  API_URL,
  classifyResponse,
  uid,
  type ChatMessage,
  type Conversation,
  type Readiness,
} from '@/components/chat/types';

const CATEGORY_LABELS: Record<string, string> = {
  rental: 'Rental agreement',
  employment: 'Employment',
  legal_notice: 'Legal notice',
  service_agreement: 'Service agreement',
};

const newConversation = (): Conversation => ({ id: uid(), title: 'New chat', docId: null, filename: null, messages: [] });

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>(() => [newConversation()]);
  const [activeId, setActiveId] = useState<string>(() => conversations[0].id);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const active = useMemo(() => conversations.find((c) => c.id === activeId) ?? conversations[0], [conversations, activeId]);

  const update = useCallback((id: string, fn: (c: Conversation) => Conversation) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? fn(c) : c)));
  }, []);

  const push = useCallback(
    (id: string, msg: Omit<ChatMessage, 'id'>) => update(id, (c) => ({ ...c, messages: [...c.messages, { ...msg, id: uid() }] })),
    [update],
  );

  useEffect(() => {
    let stop = false;
    const poll = async () => {
      try {
        const res = await fetch(`${API_URL}/health/ready`);
        if (!stop) setReadiness(res.ok ? await res.json() : { ollama: { reachable: false } });
      } catch {
        if (!stop) setReadiness({ ollama: { reachable: false } });
      }
    };
    poll();
    const t = setInterval(poll, 15000);
    return () => {
      stop = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [active.messages.length, busy]);

  const handleUpload = async (file: File) => {
    const convId = active.id;
    setBusy(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });
      const data = await res.json();
      if (res.ok && data.doc_id) {
        update(convId, (c) => ({ ...c, docId: data.doc_id, filename: data.filename, category: data.category, title: data.filename }));
        if (active.messages.length) {
          push(convId, { role: 'ai', kind: 'info', text: `${data.filename} is ready. Ask me anything about it.`, timings: data.timings, requestId: data.request_id });
        }
      } else {
        push(convId, { role: 'ai', kind: 'error', text: data.error || 'I couldn’t read that document. Please try again.' });
      }
    } catch {
      push(convId, { role: 'ai', kind: 'error', text: 'I couldn’t connect to the document service. Check that the app is running, then try again.' });
    } finally {
      setBusy(false);
    }
  };

  const handleSend = async (text?: string) => {
    const query = (text ?? input).trim();
    if (!query || !active.docId || busy) return;
    const convId = active.id;
    push(convId, { role: 'user', text: query });
    setInput('');
    setBusy(true);

    const formData = new FormData();
    formData.append('doc_id', active.docId);
    formData.append('query', query);

    try {
      const res = await fetch(`${API_URL}/chat`, { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'The document could not be analyzed.');
      const sections = Array.isArray(data.sections) && data.sections.length ? data.sections : undefined;
      const reply = data.response || 'I couldn’t generate an answer. Try asking in a different way.';
      push(convId, {
        role: 'ai',
        text: reply,
        kind: classifyResponse(reply, sections),
        sections,
        timings: data.timings,
        requestId: data.request_id,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'I couldn’t connect to the analysis service.';
      push(convId, { role: 'ai', kind: 'error', text: message });
    } finally {
      setBusy(false);
    }
  };

  const startNew = () => {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    setInput('');
    setSidebarOpen(false);
  };

  const showWelcome = active.messages.length === 0;

  return (
    <div className="relative isolate flex h-screen overflow-hidden bg-slate-950 font-sans text-white">
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

      <div className="relative z-10 flex h-full w-full">
        <Sidebar
          conversations={conversations}
          activeId={active.id}
          onSelect={(id) => {
            setActiveId(id);
            setSidebarOpen(false);
          }}
          onNew={startNew}
          readiness={readiness}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 items-center justify-between gap-2 px-3">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
                className="rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-white md:hidden"
              >
                <PanelLeftOpen className="h-5 w-5" />
              </button>
              <span className="truncate rounded-lg px-2 py-1 text-sm font-medium text-slate-200">
                {active.filename ?? 'ZeroDay PS2 Legal Triage'}
                {active.category && active.category !== 'non_legal' && (
                  <span className="ml-2 rounded-full bg-cyan-400/10 px-2 py-0.5 text-xs text-cyan-200 ring-1 ring-cyan-300/30">
                    {CATEGORY_LABELS[active.category] ?? active.category}
                  </span>
                )}
              </span>
            </div>
            <button onClick={startNew} aria-label="New chat" className="rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-white md:hidden">
              <SquarePen className="h-5 w-5" />
            </button>
          </header>

          <main ref={scrollRef} className="flex flex-1 flex-col overflow-y-auto">
            {showWelcome ? (
              <Welcome
                hasDocument={!!active.docId}
                filename={active.filename}
                onPick={(p) => handleSend(p)}
                onAttach={handleUpload}
                busy={busy}
              />
            ) : (
              <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-6">
                {active.messages.map((m) => (
                  <MessageBubble key={m.id} m={m} />
                ))}
                {busy && <TypingIndicator />}
              </div>
            )}
          </main>

          <Composer
            value={input}
            onChange={setInput}
            onSend={() => handleSend()}
            onAttach={handleUpload}
            disabled={busy}
            busy={busy}
            hasDocument={!!active.docId}
          />
        </div>
      </div>
    </div>
  );
}
