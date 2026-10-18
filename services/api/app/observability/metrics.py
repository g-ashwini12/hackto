import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from services.api.app.config.settings import settings
from services.api.app.observability.tracing import Trace


def percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 2)


def _latency_stats(values: List[float]) -> Dict[str, Any]:
    return {
        "count": len(values),
        "avg_ms": round(sum(values) / len(values), 2) if values else None,
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "p99_ms": percentile(values, 99),
        "max_ms": round(max(values), 2) if values else None,
    }


class MetricsService:
    """Local SQLite metrics for privacy-preserving observability.

    Only metadata is persisted: ids, durations, counts and model timings.
    Document text, chunks, prompts, answers and questions are never written.
    """

    _REQUEST_COLUMNS = {
        "route": "TEXT",
        "status": "TEXT",
        "model": "TEXT",
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        "cache_hit": "BOOLEAN",
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.METRICS_DB_PATH
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_metrics (
                    id TEXT PRIMARY KEY,
                    timestamp REAL,
                    doc_id TEXT,
                    processing_time REAL,
                    is_legal BOOLEAN,
                    token_count INTEGER,
                    outcome TEXT
                )
            """)
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(request_metrics)")}
            for column, col_type in self._REQUEST_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE request_metrics ADD COLUMN {column} {col_type}")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT,
                    node_name TEXT,
                    duration REAL,
                    state_snapshot TEXT,
                    timestamp REAL,
                    FOREIGN KEY(request_id) REFERENCES request_metrics(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT,
                    name TEXT,
                    start_ms REAL,
                    duration_ms REAL,
                    status TEXT,
                    slow BOOLEAN,
                    attrs TEXT,
                    timestamp REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_request ON spans(request_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_name_ts ON spans(name, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_ts ON request_metrics(timestamp)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS comparisons (
                    id TEXT PRIMARY KEY,
                    input_text TEXT,
                    model_a_tag TEXT,
                    model_a_output TEXT,
                    model_b_tag TEXT,
                    model_b_output TEXT,
                    winner_id TEXT,
                    timestamp REAL
                )
            """)

    def record_trace(
        self,
        trace: Trace,
        doc_id: str,
        is_legal: bool,
        outcome: str,
        status: str = "ok",
    ) -> None:
        """Persists one request and all of its spans in a single transaction."""
        prompt_tokens = sum(int(s.attrs.get("prompt_tokens", 0)) for s in trace.spans)
        completion_tokens = sum(int(s.attrs.get("completion_tokens", 0)) for s in trace.spans)
        cache_hit = any(s.attrs.get("cache") == "hit" for s in trace.spans)
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO request_metrics
                   (id, timestamp, doc_id, processing_time, is_legal, token_count, outcome,
                    route, status, model, prompt_tokens, completion_tokens, cache_hit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace.request_id, now, str(doc_id), trace.elapsed_ms() / 1000.0, bool(is_legal),
                    prompt_tokens + completion_tokens, str(outcome), trace.route, status,
                    settings.OLLAMA_MODEL, prompt_tokens, completion_tokens, cache_hit,
                ),
            )
            conn.executemany(
                """INSERT INTO spans (request_id, name, start_ms, duration_ms, status, slow, attrs, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (trace.request_id, s.name, s.start_ms, s.duration_ms, s.status, s.slow, json.dumps(s.attrs), now)
                    for s in trace.spans
                ],
            )

    def log_request(self, request_id: str, doc_id: str, duration: float, is_legal: bool, outcome: str, token_count: int = 0):
        """Logs request metadata without storing document text."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO request_metrics (id, timestamp, doc_id, processing_time, is_legal, token_count, outcome) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(request_id), time.time(), str(doc_id), float(duration), bool(is_legal), int(token_count), str(outcome)),
            )

    def log_comparison(self, comparison_id: str, input_text: str, model_a_tag: str, model_a_output: str, model_b_tag: str, model_b_output: str):
        """Logs A/B test results."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO comparisons (id, input_text, model_a_tag, model_a_output, model_b_tag, model_b_output, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (comparison_id, input_text, model_a_tag, model_a_output, model_b_tag, model_b_output, time.time())
            )

    def get_aggregate_metrics(self, window_s: Optional[float] = None) -> Dict[str, Any]:
        """Summary statistics for the dashboard (backwards-compatible keys kept)."""
        since = time.time() - window_s if window_s else 0
        with self._connect() as conn:
            row = conn.execute(
                """SELECT AVG(processing_time) AS avg_latency, SUM(token_count) AS total_tokens,
                          COUNT(*) AS total_requests,
                          SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
                          SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits
                   FROM request_metrics WHERE timestamp >= ?""",
                (since,),
            ).fetchone()
            latencies = [r[0] * 1000.0 for r in conn.execute(
                "SELECT processing_time FROM request_metrics WHERE timestamp >= ? AND route = '/chat'", (since,)
            )]
            tps = [json.loads(r[0]).get("tokens_per_s") for r in conn.execute(
                "SELECT attrs FROM spans WHERE timestamp >= ? AND name = 'llm.answer'", (since,)
            )]
        result = dict(row)
        total = result["total_requests"] or 0
        result["error_rate"] = round((result["errors"] or 0) / total, 4) if total else 0.0
        result["chat_latency"] = _latency_stats(latencies)
        tps = [t for t in tps if t]
        result["avg_tokens_per_s"] = round(sum(tps) / len(tps), 2) if tps else None
        return result

    def get_stage_latency(self, window_s: Optional[float] = None) -> Dict[str, Any]:
        """p50/p95/p99 per pipeline stage, plus how often each stage blew its budget."""
        since = time.time() - window_s if window_s else 0
        by_stage: Dict[str, List[float]] = {}
        slow: Dict[str, int] = {}
        with self._connect() as conn:
            for r in conn.execute("SELECT name, duration_ms, slow FROM spans WHERE timestamp >= ?", (since,)):
                by_stage.setdefault(r["name"], []).append(r["duration_ms"])
                slow[r["name"]] = slow.get(r["name"], 0) + int(bool(r["slow"]))
        return {
            name: {**_latency_stats(vals), "budget_ms": settings.LATENCY_BUDGETS_MS.get(name), "over_budget": slow[name]}
            for name, vals in sorted(by_stage.items())
        }

    def get_recent_logs(self, limit=50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM request_metrics ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in rows]

    def get_trace_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        """Ordered spans (waterfall) for one request."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, start_ms, duration_ms, status, slow, attrs FROM spans WHERE request_id = ? ORDER BY start_ms ASC",
                (request_id,),
            )
            return [{**dict(r), "attrs": json.loads(r["attrs"] or "{}")} for r in rows]

    def purge(self, older_than_s: float) -> int:
        cutoff = time.time() - older_than_s
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM spans WHERE timestamp < ?", (cutoff,))
            cur = conn.execute("DELETE FROM request_metrics WHERE timestamp < ?", (cutoff,))
            return cur.rowcount


metrics_service = MetricsService()
