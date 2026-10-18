'use client';

import { useEffect, useRef } from 'react';
import { ArrowUp, Loader2, Paperclip } from 'lucide-react';

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onAttach: (file: File) => void;
  disabled: boolean;
  busy: boolean;
  hasDocument: boolean;
};

export default function Composer({ value, onChange, onSend, onAttach, disabled, busy, hasDocument }: Props) {
  const textRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const canSend = hasDocument && !busy && value.trim().length > 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      <div className="group rounded-3xl border border-white/15 bg-slate-900/70 p-2 shadow-2xl shadow-indigo-950/40 backdrop-blur-xl transition focus-within:border-cyan-400/50">
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            title="Attach a PDF or TXT"
            aria-label="Attach a PDF or TXT document"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-40"
          >
            <Paperclip className="h-5 w-5" />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onAttach(f);
              e.target.value = '';
            }}
          />
          <textarea
            ref={textRef}
            rows={1}
            value={value}
            disabled={disabled}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (canSend) onSend();
              }
            }}
            placeholder={hasDocument ? 'Ask about your document…' : 'Attach a document to start'}
            aria-label="Message"
            className="max-h-[200px] flex-1 resize-none bg-transparent py-2.5 text-[15px] leading-6 text-white outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!canSend}
            aria-label="Send message"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-slate-950 transition hover:bg-cyan-200 disabled:bg-white/15 disabled:text-slate-400"
          >
            {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <ArrowUp className="h-5 w-5" />}
          </button>
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-slate-400">
        Runs on your device with a local Gemma model. For information only, not legal advice.
      </p>
    </div>
  );
}
