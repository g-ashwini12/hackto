# UI Structure

## Implemented: chat layout (`apps/app/app/page.tsx`, `apps/app/components/chat/`)

The UI now follows a familiar ChatGPT-style layout. The Aurora background is unchanged
(same component and props).

| Area | Component | What it shows |
|---|---|---|
| Left sidebar | `Sidebar.tsx` | New chat, recent chats (one per document), live model status from `GET /health/ready` (ready / loading / offline), "on-device" note |
| Header | `page.tsx` | Active document name + category chip |
| Welcome screen | `Welcome.tsx` + `WelcomeScene.tsx` | Three.js scene (`@react-three/fiber`): floating glass document with a highlighted clause, wireframe core with orbit rings, particle field, pointer parallax. Loaded client-only with `next/dynamic`. Respects `prefers-reduced-motion`. Before upload: drag-and-drop zone. After upload: four suggested-question cards |
| Thread | `MessageBubble.tsx` | User messages as pills; assistant answers with avatar, collapsible "Found in your document" evidence, warning when nothing matched, separate callouts for **Needs a lawyer** (escalation), **Not in the document** (silent) and errors, timing chips (`total`, `Model`, `Search`, `Check`, over-budget flag) from the `timings` field, copy button |
| Composer | `Composer.tsx` | Auto-growing textarea (Enter sends, Shift+Enter newline), attach button, send/spinner, not-legal-advice note |

Mobile: the sidebar becomes a slide-over drawer.

## Future option: split-pane analysis layout

The rest of this document is the earlier design for a split source/analysis layout.
It is kept as a possible next step (e.g. a "View source" panel); it is not implemented.

## Why change the structure

PS2 judges look for things the current single chat column cannot show well:

| PS2 requirement | Current UI | Gap |
|---|---|---|
| L5 / rubric 2: cited passages beside the source | Evidence hidden in a collapsed `<details>` | Source is never visible next to the claim |
| L6: explicit text vs interpretation | One "Answer" card | No separation |
| L7 / L8: ambiguity, silence, escalation | Plain text reply | Refusals look like errors |
| L9: demonstrable privacy | Nothing | No local/offline indicator |
| "Report memory and speed" | Nothing | No latency/token data shown |
| Usability (8 pts) | Single scrolling column | No prioritisation of risks/obligations |

## Target layout

```
+--------------------------------------------------------------------------------+
| Header: title | PrivacyBadge (Local · Offline-ready · gemma3:1b) | Upload    |
+-----------------------------+--------------------------------------------------+
| DocumentPane (left, 45%)    | AnalysisPane (right, 55%)                        |
|                             |  Tabs: [Ask] [Key terms] [Risks] [Performance]   |
|  - filename, category chip  |                                                  |
|  - scrollable source text   |  Ask tab:                                        |
|    split by chunk/clause    |   ConversationThread                             |
|  - cited passages           |    AnswerCard                                    |
|    highlighted; clicking a  |     - "What the document says" (quoted, cited)   |
|    citation scrolls here    |     - "Possible interpretation" (labelled)       |
|                             |     - Confidence / Grounded badge                |
|                             |     - LatencyChip (e.g. 2.4 s · 38 tok/s)        |
|                             |    SilentCard  ("The document doesn't say ...")  |
|                             |    EscalationCard (refusal + who to ask)         |
|                             |   QuestionComposer + suggested questions         |
+-----------------------------+--------------------------------------------------+
| Footer: "For information only; not legal advice." · request id of last answer  |
+--------------------------------------------------------------------------------+
```

On narrow screens the two panes stack: AnalysisPane first, DocumentPane behind a
"View source" toggle.

## Component tree

```
app/
  page.tsx                      -> <Workspace/> only (state lives in hooks)
  components/
    layout/Header.tsx
    layout/PrivacyBadge.tsx     GET /health/ready -> local runtime, model loaded
    upload/UploadButton.tsx     POST /upload (shows category + upload timing)
    document/DocumentPane.tsx   source text, clause anchors, highlight on citation
    analysis/AnalysisPane.tsx   tabs container
    analysis/ConversationThread.tsx
    analysis/AnswerCard.tsx     sections[].content / evidence / verified
    analysis/SilentCard.tsx     verified=false or no lexical hits
    analysis/EscalationCard.tsx response for policy refusals (sections = [])
    analysis/LatencyChip.tsx    timings.total_ms + slow_stages
    perf/PerformanceTab.tsx     GET /dashboard/metrics, /dashboard/latency
    perf/TraceWaterfall.tsx     GET /dashboard/trace/{request_id}
  hooks/
    useDocument.ts              upload state, doc_id, category
    useChat.ts                  messages, send(), per-message request_id + timings
    useApi.ts                   base URL from NEXT_PUBLIC_API_URL (default 127.0.0.1:8000)
  lib/types.ts                  ChatResponse, Timings, StageLatency, Span
```

## Data contract the UI can rely on (already returned by the API)

`POST /chat` and `POST /upload` responses now also include (existing fields unchanged):

```json
{
  "response": "...",
  "sections": [{"title": "Answer", "content": "...", "evidence": ["..."], "verified": true}],
  "request_id": "6c1f...",
  "timings": {
    "request_id": "6c1f...",
    "total_ms": 2410.3,
    "stages_ms": {"retrieval.query": 0.4, "llm.answer": 2380.1, "verify.grounding": 0.2},
    "slow_stages": []
  }
}
```

Headers: `Server-Timing` (per stage), `X-Request-ID`, `X-Response-Time-Ms`.

Dashboard endpoints for the Performance tab:

- `GET /dashboard/metrics?window_s=3600` – requests, error rate, cache hits, chat p50/p95/p99, avg tokens/s
- `GET /dashboard/latency?window_s=3600` – per-stage p50/p95/p99, budget, over-budget count
- `GET /dashboard/trace/{request_id}` – ordered spans for a waterfall
- `GET /health/ready` – Ollama reachable, model resident, warm-up cost

## Performance tab

1. Four stat tiles: chat p50, chat p95, avg tokens/s, cache-hit rate.
2. Stage table from `/dashboard/latency`: stage, p50, p95, budget, over-budget count
   (red when `over_budget > 0`).
3. TraceWaterfall for the selected answer: horizontal bars positioned by `start_ms`,
   width = `duration_ms`, `llm.*` bars labelled with tokens and tokens/s.
4. Privacy note: "All numbers are computed locally from `metrics.db`; no document text is stored."

## Perceived-latency rules for the UI

- Show the upload as two steps: "Reading document" then "Classifying" (both happen at upload,
  so the first question is fast).
- Disable only the composer while waiting, not the whole page; show elapsed seconds.
- Escalation answers return in a few ms (no model call): render them immediately.
- Poll `/health/ready` once on load; if the model is not resident, show "Warming up model".

## Accessibility

- Tabs and citations keyboard-navigable; citations are buttons with `aria-controls` pointing at
  the highlighted passage.
- Status chips use text, not colour alone (e.g. "Grounded", "Not found in document").
- Respect `prefers-reduced-motion` for Aurora / SplitText.
