# Observability and Latency (PS2)

Everything here runs on the device. Metrics live in a local SQLite file
(`metrics.db`) and JSON manifests (`manifests/`). Neither contains document
text, chunks, prompts, answers, names or the user's question.

## What is measured

Each request (`/upload`, `/chat`) gets a **trace**: an ordered list of timed
**spans** (`services/api/app/observability/tracing.py`).

| Span | What it times | Attributes (metadata only) |
|---|---|---|
| `request.upload` / `request.chat` | Whole pipeline | `query_chars` |
| `upload.save` | Writing the upload to disk | `bytes` |
| `ingest.hash` | SHA-256 of file (cache key) | `bytes` |
| `ingest.cache` | Cache hit, parse skipped | `cache`, `chunks` |
| `ingest.extract` | PDF/TXT extraction | `chars` |
| `ingest.chunk` | Sliding-window chunking | `chunks` |
| `retrieval.index` | BM25 (or Chroma) indexing | `backend`, `chunks` |
| `retrieval.query` | Top-k retrieval | `chunks`, `lexical_hits` |
| `route.cache` | Cached document category reused | `category` |
| `llm.classify` / `llm.answer` | Local Gemma call via Ollama | `prompt_tokens`, `completion_tokens`, `load_ms`, `prompt_eval_ms`, `eval_ms`, `model_total_ms`, `tokens_per_s` |
| `verify.grounding` | Evidence check | `grounded`, `evidence` |
| `policy.input` / `policy.output` | Verdict-question gate / output filter | `escalated` / `blocked` |
| `node.<name>` | Each LangGraph node | – |

Span attributes pass through an allow-list (`_safe_attrs`): only numbers,
booleans and a few short identifier strings (`model`, `category`, `backend`,
`outcome`, `cache`) are kept, so free text can't reach the database by accident.
A unit test plants a unique name in a document and asserts it never appears in
`request_metrics` or `spans`.

## Where to see it

| Surface | How |
|---|---|
| Response body | `request_id` and `timings` (`total_ms`, `stages_ms`, `slow_stages`) on `/upload` and `/chat` |
| Response headers | `Server-Timing` (shows in browser DevTools → Network → Timing), `X-Request-ID`, `X-Response-Time-Ms` |
| `GET /dashboard/metrics?window_s=3600` | requests, errors, error rate, cache hits, chat p50/p95/p99/max, avg tokens/s |
| `GET /dashboard/latency?window_s=3600` | per-stage count, avg, p50, p95, p99, max, budget, over-budget count |
| `GET /dashboard/trace/{request_id}` | span waterfall for one request |
| `GET /dashboard/logs` | recent requests (ids, durations, outcome, token counts) |
| `GET /health/ready` | Ollama reachable, model resident in memory, VRAM/size, warm-up cost |
| Server log | one JSON line per span (`TRACE_LOG_SPANS=true`) |
| Manifests | `manifests/<request_id>-<stage>.json`: model, decoding config, prompt SHA-256, token counts and timings |

Latency budgets per stage are set in `LATENCY_BUDGETS_MS`
(`services/api/app/config/settings.py`). Spans over budget are flagged `slow`
and counted in `/dashboard/latency`.

## Latency changes

| Change | Before | After |
|---|---|---|
| Parse + chunk + index | On every question (and Chroma re-`add` of the same ids) | Once per document, cached by content SHA-256 (`services/api/app/services/documents.py`) |
| Document classification | One extra LLM call on every question | Once, at upload time; questions reuse it |
| LLM calls per question | 2 | 1 |
| Verdict questions ("Is this enforceable?") | Full pipeline, then output filter | Refused in `policy_gate` before any parsing or model call (~ms) |
| Model cold start | First question pays model load | Background warm-up at API start; `OLLAMA_KEEP_ALIVE=30m` |
| Classification decode | Up to 256 tokens | `CLASSIFY_MAX_TOKENS=8` |
| Retrieval | ChromaDB default embedder (ONNX model download on first use) | In-process BM25 by default, no model, no network; Chroma still available via `RETRIEVAL_BACKEND=chroma` (telemetry off) |
| Event loop | `async def` endpoints made blocking model calls | Sync endpoints run in the worker pool; health/dashboard stay responsive during inference |
| Metrics writes | One SQLite connection + commit per node, full state snapshot JSON | One transaction per request, WAL mode, metadata only |
| Ollama host | `OLLAMA_BASE_URL` was ignored | `ollama.Client(host=OLLAMA_BASE_URL)` |

## Benchmark

```bash
./run.sh                                  # or start the API on 127.0.0.1:8000
python scripts/benchmark.py --doc samples/sample_rental_agreement.txt --rounds 3 --out bench.json
```

Reports upload time, chat end-to-end p50/p95, per-stage p50/p95 from
`Server-Timing`, average tokens/s and whether the model is resident (with its size).
Record results with your OS, CPU/GPU and model tag; see `docs/ps2-alignment.md`.

## Privacy notes

- The observability stack makes no network calls. There is no exporter, no telemetry SDK.
- ChromaDB anonymous telemetry is disabled if that backend is enabled.
- `metrics.db`, `manifests/` and `uploads/` are git-ignored; they can be deleted at any time.
