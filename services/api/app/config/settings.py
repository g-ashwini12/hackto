import os
from typing import Dict, List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "ZeroDay PS2"
    DEBUG: bool = True

    # Privacy & Local Constraints
    BIND_ADDRESS: str = "127.0.0.1"
    BIND_PORT: int = 8000
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 20
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt"]

    # Ollama Config (local runtime only)
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    # Keep the model resident between questions to avoid cold-start load time.
    OLLAMA_KEEP_ALIVE: str = "30m"
    WARMUP_ON_STARTUP: bool = True
    LLM_TEMPERATURE: float = 0.0
    LLM_SEED: int = 42
    LLM_CONTEXT_WINDOW: int = 2048
    LLM_MAX_TOKENS: int = 256
    CLASSIFY_MAX_TOKENS: int = 8
    CLASSIFY_SAMPLE_CHARS: int = 1200

    # Ingestion & Retrieval
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_K: int = 3
    # "bm25": in-process lexical search, no model download, no network.
    # "chroma": ChromaDB with its default embedding model (downloaded once at setup).
    RETRIEVAL_BACKEND: str = "bm25"
    DOC_CACHE_SIZE: int = 32

    # Observability (local SQLite + JSON manifests; never stores document content)
    METRICS_DB_PATH: str = "metrics.db"
    MANIFEST_DIR: str = "manifests"
    TRACE_LOG_SPANS: bool = True
    TRACE_STRING_ATTRS: List[str] = ["model", "category", "backend", "outcome", "cache"]
    # Per-stage latency budgets; spans over budget are flagged "slow".
    LATENCY_BUDGETS_MS: Dict[str, float] = {
        "ingest.extract": 1500,
        "ingest.chunk": 100,
        "retrieval.index": 1000,
        "retrieval.coverage": 20,
        "retrieval.query": 150,
        "llm.classify": 3000,
        "llm.answer": 8000,
        "verify.grounding": 50,
        "policy.output": 10,
        "request.chat": 10000,
        "request.upload": 6000,
    }

    model_config = {
        "extra": "ignore",
        "env_file": ".env"
    }


settings = Settings()
