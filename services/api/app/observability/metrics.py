import sqlite3
import time
import json
from services.api.app.config.settings import settings

class MetricsService:
    """Local SQLite-based metrics for privacy-preserving observability."""

    def __init__(self):
        self.db_path = "metrics.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

    def log_request(self, request_id: str, doc_id: str, duration: float, is_legal: bool, outcome: str, token_count: int = 0):
        """Logs request metadata without storing document text."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO request_metrics VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(request_id),
                    time.time(),
                    str(doc_id),
                    float(duration),
                    bool(is_legal),
                    int(token_count),
                    str(outcome)
                )
            )
            conn.commit()

    def log_trace(self, request_id: str, node_name: str, duration: float, state_snapshot: dict):
        """Logs a node transition in the orchestration graph."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO traces (request_id, node_name, duration, state_snapshot, timestamp) VALUES (?, ?, ?, ?, ?)",
                (request_id, node_name, duration, json.dumps(state_snapshot), time.time())
            )
            conn.commit()

    def log_comparison(self, comparison_id: str, input_text: str, model_a_tag: str, model_a_output: str, model_b_tag: str, model_b_output: str):
        """Logs A/B test results."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO comparisons (id, input_text, model_a_tag, model_a_output, model_b_tag, model_b_output, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (comparison_id, input_text, model_a_tag, model_a_output, model_b_tag, model_b_output, time.time())
            )
            conn.commit()

    def get_aggregate_metrics(self):
        """Calculates summary statistics for the dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT AVG(processing_time) as avg_latency, SUM(token_count) as total_tokens, COUNT(*) as total_requests FROM request_metrics")
            return dict(cursor.fetchone())

    def get_recent_logs(self, limit=50):
        """Returns the most recent requests."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM request_metrics ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trace_for_request(self, request_id: str):
        """Returns the sequence of nodes for a specific request."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traces WHERE request_id = ? ORDER BY timestamp ASC", (request_id,))
            return [dict(row) for row in cursor.fetchall()]

metrics_service = MetricsService()
