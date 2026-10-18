export const API_URL = 'http://127.0.0.1:8000';

export type AnalysisSection = {
  title: string;
  content: string;
  evidence: string[];
  verified: boolean;
};

export type Timings = {
  total_ms?: number;
  stages_ms?: Record<string, number>;
  slow_stages?: string[];
};

export type MessageKind = 'answer' | 'escalation' | 'silent' | 'info' | 'error';

export type ChatMessage = {
  id: string;
  role: 'user' | 'ai';
  text: string;
  kind?: MessageKind;
  sections?: AnalysisSection[];
  timings?: Timings;
  requestId?: string;
};

export type Conversation = {
  id: string;
  title: string;
  docId: string | null;
  filename: string | null;
  category?: string | null;
  messages: ChatMessage[];
};

export type Readiness = {
  model?: string;
  ollama?: { reachable?: boolean; model_loaded?: boolean };
};

let counter = 0;
export const uid = () => `id-${++counter}`;

export function classifyResponse(text: string, sections?: AnalysisSection[]): MessageKind {
  if (sections && sections.length) return 'answer';
  if (/consult a qualified lawyer|can't decide whether/i.test(text)) return 'escalation';
  if (/appears to be silent/i.test(text)) return 'silent';
  return 'info';
}

export function formatMs(ms?: number) {
  if (ms === undefined) return '';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}
