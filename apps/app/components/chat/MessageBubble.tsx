'use client';

import { AlertTriangle, CheckCircle2, Copy, Gauge, Scale, SearchX, ShieldCheck } from 'lucide-react';
import { formatMs, type ChatMessage } from './types';

const STAGE_LABELS: Record<string, string> = {
  'llm.answer': 'Model',
  'llm.classify': 'Classify',
  'retrieval.query': 'Search',
  'verify.grounding': 'Check',
};

function TimingChips({ m }: { m: ChatMessage }) {
  const t = m.timings;
  if (!t?.total_ms) return null;
  const stages = Object.entries(t.stages_ms ?? {}).filter(([k]) => k in STAGE_LABELS);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400" title={m.requestId ? `Request ${m.requestId}` : undefined}>
      <span className="inline-flex items-center gap-1 rounded-full bg-white/5 px-2 py-0.5 ring-1 ring-white/10">
        <Gauge className="h-3 w-3" /> {formatMs(t.total_ms)}
      </span>
      {stages.map(([k, v]) => (
        <span key={k} className="rounded-full bg-white/5 px-2 py-0.5 ring-1 ring-white/10">
          {STAGE_LABELS[k]} {formatMs(v)}
        </span>
      ))}
      {t.slow_stages && t.slow_stages.length > 0 && (
        <span className="rounded-full bg-amber-400/10 px-2 py-0.5 text-amber-300 ring-1 ring-amber-300/30">over budget</span>
      )}
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex gap-4">
      <Avatar />
      <div className="flex items-center gap-1.5 pt-3" aria-label="Thinking">
        {[0, 150, 300].map((d) => (
          <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-slate-300" style={{ animationDelay: `${d}ms` }} />
        ))}
      </div>
    </div>
  );
}

function Avatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-400 ring-1 ring-white/20">
      <ShieldCheck className="h-4 w-4 text-white" />
    </div>
  );
}

export default function MessageBubble({ m }: { m: ChatMessage }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-3xl bg-white/10 px-5 py-2.5 text-[15px] leading-6 text-white ring-1 ring-white/10 backdrop-blur-md">
          {m.text}
        </div>
      </div>
    );
  }

  const section = m.sections?.[0];
  const callout =
    m.kind === 'escalation'
      ? { icon: Scale, cls: 'border-violet-400/30 bg-violet-500/10 text-violet-100', label: 'Needs a lawyer' }
      : m.kind === 'silent'
        ? { icon: SearchX, cls: 'border-slate-400/30 bg-slate-500/10 text-slate-100', label: 'Not in the document' }
        : m.kind === 'error'
          ? { icon: AlertTriangle, cls: 'border-rose-400/30 bg-rose-500/10 text-rose-100', label: 'Something went wrong' }
          : null;

  return (
    <div className="group flex gap-4">
      <Avatar />
      <div className="min-w-0 flex-1 pt-1">
        {callout ? (
          <div className={`rounded-2xl border p-4 backdrop-blur-md ${callout.cls}`}>
            <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-80">
              <callout.icon className="h-3.5 w-3.5" /> {callout.label}
            </div>
            <p className="whitespace-pre-wrap text-[15px] leading-7">{m.text}</p>
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-[15px] leading-7 text-slate-100">{section?.content ?? m.text}</p>
        )}

        {section && (
          <div className="mt-3">
            {section.evidence.length > 0 ? (
              <details className="group/ev rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-md open:bg-slate-900/70">
                <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-xs font-medium text-slate-300 hover:text-white">
                  {section.verified ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />}
                  {section.verified ? 'Found in your document' : 'Could not fully match to the text'}
                  <span className="text-slate-500">· {section.evidence.length} passage{section.evidence.length > 1 ? 's' : ''}</span>
                </summary>
                <ul className="space-y-2 px-4 pb-4">
                  {section.evidence.map((q, i) => (
                    <li key={i} className="border-l-2 border-cyan-400/60 pl-3 text-sm leading-6 text-slate-300">
                      “{q}”
                    </li>
                  ))}
                </ul>
              </details>
            ) : (
              <p className="flex items-center gap-2 text-xs text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5" /> No matching passage found. Treat this answer with caution.
              </p>
            )}
          </div>
        )}

        <div className="flex items-center gap-2">
          <TimingChips m={m} />
          <button
            onClick={() => navigator.clipboard?.writeText(section?.content ?? m.text)}
            aria-label="Copy answer"
            className="mt-3 rounded-md p-1 text-slate-500 opacity-0 transition hover:bg-white/10 hover:text-white focus:opacity-100 group-hover:opacity-100"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
