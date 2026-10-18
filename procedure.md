# ZeroDay PS2: Project Implementation Procedure

## 🚀 Project Overview
ZeroDay PS2 is a private, on-device legal document triage agent. It is designed to process legal documents locally using a Compound AI System architecture, ensuring that no sensitive data ever leaves the user's machine.

## 🛠️ Technical Architecture
The system follows a multi-layered approach:
1. **Ingestion Layer**: Local PDF/TXT extraction and context-aware chunking.
2. **Retrieval Layer**: In-process BM25 over each document's chunks (no embedding model, no network), plus a coverage check that answers "the document is silent" when a topic never appears. ChromaDB is optional (`RETRIEVAL_BACKEND=chroma`, telemetry off).
3. **Orchestration Layer**: A LangGraph state machine that routes queries, runs parallel analysis, and merges results.
4. **Verification Layer**: A grounding service that ensures every AI claim is backed by evidence in the text.
5. **Safety Layer**: A policy filter that blocks the AI from giving legal verdicts or advice.
6. **Observability Layer**: Per-stage trace spans, `Server-Timing` headers, p50/p95/p99 latency, Ollama token/timing data, SQLite metrics and JSON manifests. Metadata only, never document text or prompts. See `docs/observability-and-latency.md`.

## 📝 Step-by-Step Implementation Procedure

### Phase 1: Foundation & Setup
- **Monorepo Initialization**: Set up the project structure with separate `apps/web` and `services/api`.
- **Environment Configuration**: Created `scripts/setup.sh` to handle the installation of Ollama, Python dependencies, and the Gemma model.
- **Strict Privacy Settings**: Configured the system to bind to `127.0.0.1` and disabled all cloud telemetry (`NEXT_TELEMETRY_DISABLED=1`).
- **Config Management**: Implemented a Pydantic-based settings system for reproducibility (Fixed seed, Temp 0).

### Phase 2: Ingestion & Basic Inference
- **Local Extraction**: Built the `IngestionService` to handle PDF and TXT files locally.
- **Smart Chunking**: Implemented a sliding-window chunker to maintain context across segments.
- **Inference Wrapper**: Created an `InferenceClient` for Ollama, including a `MockInferenceClient` for deterministic unit testing.
- **Prompt Engineering**: Developed versioned templates for classification and analysis with few-shot examples.

### Phase 3: RAG & Orchestration
- **Vector Store**: Integrated ChromaDB for local embedding storage and cosine similarity retrieval.
- **State Machine**: Designed the LangGraph orchestrator.
    - **Routing**: Implemented a classifier node to reject non-legal documents.
    - **Parallel Analysis**: Created a fan-out pattern to analyze Clauses, Risks, Obligations, and Deadlines concurrently.
- **Integration**: Connected retrieval to analysis to ensure the model only sees relevant document fragments.

### Phase 4: Verification & Safety
- **Evidence Grounding**: Built the `VerificationService` to prevent hallucinations by checking claims against the original text.
- **Safety Guardrails**: Implemented `SafetyService` to scan and block forbidden terms like "illegal" or "you will win".
- **Local Observability**: Added SQLite metrics for performance tracking and JSON manifests for auditability.

### Phase 5: Frontend Integration
- **API Development**: Created FastAPI endpoints for `/upload` and `/chat`.
- **UI Development**: Built a Next.js chat interface with Tailwind CSS.
- **Privacy Polish**: Removed all external CDNs and Google Fonts, using system-native fonts only.

## 🚀 How to Run the Project

1. **Install Ollama**: Download from ollama.com.
2. **Prepare the backend environment** (one time):
   ```bash
   cd /path/to/zeroday_ps2
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Prepare the frontend dependencies** (one time):
   ```bash
   cd apps/app
   npm install
   ```
4. **Start the app** from the project root:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
   The launcher starts Ollama if needed, pulls `gemma3:1b` if it is missing, then starts the API and website. Open http://localhost:3000 and press Ctrl+C in the terminal to stop.

## 🛡️ Privacy & Compliance Verification
- [x] All traffic stays on `127.0.0.1`.
- [x] No cloud LLM calls.
- [x] No telemetry from the API or ChromaDB.
- [ ] Remote fonts: `apps/app/app/layout.tsx` still uses `next/font/google` (fetched at build time, self-hosted at runtime). Switch to `next/font/local` or system fonts before the offline demo.
- [x] Answers are checked against retrieved passages; topics the document never mentions get a "document is silent" answer without a model call.
- [x] Verdict questions (enforceable, legal, should I sign, will I win) are refused before any model call, with escalation to a qualified lawyer / DLSA.

Further reading: `docs/ps2-alignment.md`, `docs/observability-and-latency.md`, `docs/ui-structure.md`.
