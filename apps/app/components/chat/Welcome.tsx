'use client';

import dynamic from 'next/dynamic';
import { CalendarClock, FileUp, Gavel, Lock, ScrollText, Wallet } from 'lucide-react';
import SplitText from '@/components/SplitText';

const WelcomeScene = dynamic(() => import('./WelcomeScene'), {
  ssr: false,
  loading: () => <div className="h-full w-full" />,
});

const SUGGESTIONS = [
  { icon: Wallet, title: 'Money', prompt: 'How much do I have to pay, and when?' },
  { icon: CalendarClock, title: 'Deadlines', prompt: 'What deadlines or notice periods does this set?' },
  { icon: ScrollText, title: 'Ending it', prompt: 'How can this agreement be terminated?' },
  { icon: Gavel, title: 'Penalties', prompt: 'What penalties or fees could I be charged?' },
];

type Props = {
  hasDocument: boolean;
  filename: string | null;
  onPick: (prompt: string) => void;
  onAttach: (file: File) => void;
  busy: boolean;
};

export default function Welcome({ hasDocument, filename, onPick, onAttach, busy }: Props) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-6">
      <div className="relative h-56 w-full max-w-md sm:h-64" aria-hidden="true">
        <div className="absolute inset-x-10 bottom-4 h-16 rounded-full bg-indigo-500/20 blur-3xl" />
        <WelcomeScene />
      </div>

      <h1 className="mt-2 text-center text-3xl font-semibold tracking-tight sm:text-4xl">
        <SplitText
          text={hasDocument ? 'What do you want to know?' : 'Understand any contract, privately.'}
          className="inline-block"
          tag="span"
          textAlign="center"
          trigger="load"
          splitType="words"
          delay={60}
          duration={0.8}
        />
      </h1>
      <p className="mt-3 max-w-xl text-center text-sm leading-6 text-slate-300">
        {hasDocument
          ? <>Asking about <span className="font-medium text-cyan-200">{filename}</span>. Every answer shows the passage it came from.</>
          : 'Upload a lease, job offer or legal notice. A Gemma model on this device explains it in plain language and shows you the exact text.'}
      </p>

      {!hasDocument ? (
        <label
          className={`mt-8 flex w-full max-w-xl cursor-pointer flex-col items-center gap-3 rounded-3xl border border-dashed border-white/20 bg-slate-900/50 p-8 text-center backdrop-blur-md transition hover:border-cyan-300/60 hover:bg-slate-900/70 ${busy ? 'pointer-events-none opacity-60' : ''}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) onAttach(f);
          }}
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/40 to-cyan-400/30 ring-1 ring-white/20">
            <FileUp className="h-6 w-6 text-white" />
          </span>
          <span className="text-sm font-medium">{busy ? 'Reading your document…' : 'Drop a PDF or TXT here, or click to browse'}</span>
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <Lock className="h-3.5 w-3.5" /> Processed locally. Not uploaded to any server.
          </span>
          <input
            type="file"
            accept=".pdf,.txt"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onAttach(f);
              e.target.value = '';
            }}
          />
        </label>
      ) : (
        <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
          {SUGGESTIONS.map(({ icon: Icon, title, prompt }) => (
            <button
              key={title}
              onClick={() => onPick(prompt)}
              disabled={busy}
              className="group flex items-start gap-3 rounded-2xl border border-white/10 bg-slate-900/50 p-4 text-left backdrop-blur-md transition hover:-translate-y-0.5 hover:border-cyan-300/40 hover:bg-slate-900/70 disabled:opacity-50"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/5 ring-1 ring-white/10 transition group-hover:bg-cyan-400/15">
                <Icon className="h-4.5 w-4.5 text-cyan-200" />
              </span>
              <span>
                <span className="block text-sm font-medium text-white">{title}</span>
                <span className="block text-sm text-slate-400">{prompt}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
