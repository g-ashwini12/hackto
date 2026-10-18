'use client';

import { FileText, MessageSquare, PanelLeftClose, Plus, ShieldCheck } from 'lucide-react';
import type { Conversation, Readiness } from './types';

type Props = {
  conversations: Conversation[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  readiness: Readiness | null;
  open: boolean;
  onClose: () => void;
};

export default function Sidebar({ conversations, activeId, onSelect, onNew, readiness, open, onClose }: Props) {
  const reachable = readiness?.ollama?.reachable;
  const loaded = readiness?.ollama?.model_loaded;
  const status = readiness === null ? 'Checking…' : !reachable ? 'Model offline' : loaded ? 'Model ready' : 'Model loading';
  const dot = readiness === null ? 'bg-slate-400' : !reachable ? 'bg-rose-400' : loaded ? 'bg-emerald-400' : 'bg-amber-400';

  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 z-30 bg-black/50 backdrop-blur-sm transition md:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-white/10 bg-slate-950/70 backdrop-blur-xl transition-transform md:static md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between p-3">
          <div className="flex items-center gap-2 px-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-400 shadow-lg shadow-indigo-900/50">
              <ShieldCheck className="h-4.5 w-4.5 text-white" />
            </div>
            <span className="text-sm font-semibold tracking-tight">ZeroDay Legal</span>
          </div>
          <button onClick={onClose} aria-label="Close sidebar" className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white md:hidden">
            <PanelLeftClose className="h-5 w-5" />
          </button>
        </div>

        <div className="px-3">
          <button
            onClick={onNew}
            className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm font-medium transition hover:bg-white/10"
          >
            <Plus className="h-4 w-4" /> New chat
          </button>
        </div>

        <nav className="mt-4 flex-1 overflow-y-auto px-3" aria-label="Chats">
          <p className="px-2 pb-2 text-xs font-medium uppercase tracking-wider text-slate-500">Recent</p>
          <ul className="space-y-1">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => onSelect(c.id)}
                  aria-current={c.id === activeId ? 'page' : undefined}
                  className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition ${c.id === activeId ? 'bg-white/10 text-white' : 'text-slate-300 hover:bg-white/5'}`}
                >
                  {c.filename ? <FileText className="h-4 w-4 shrink-0 text-cyan-300" /> : <MessageSquare className="h-4 w-4 shrink-0 text-slate-400" />}
                  <span className="truncate">{c.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="m-3 rounded-2xl border border-white/10 bg-white/5 p-3 text-xs">
          <div className="flex items-center gap-2 font-medium text-slate-200">
            <span className={`h-2 w-2 rounded-full ${dot}`} />
            {status}
          </div>
          <p className="mt-1 text-slate-400">{readiness?.model ?? 'gemma'} · on-device · nothing leaves this computer</p>
        </div>
      </aside>
    </>
  );
}
