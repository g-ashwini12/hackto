"""Privacy-safe request tracing.

A Trace is a list of timed spans for one request. Spans carry only
metadata (durations, counts, sizes, model timings) and never document
text, chunks, prompts, answers or the user's question.
"""
import contextvars
import functools
import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional

from services.api.app.config.settings import settings

logger = logging.getLogger("zeroday.trace")

_ALLOWED_ATTR_TYPES = (int, float, bool)


def _safe_attrs(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Keep numeric/boolean values and short identifier-like strings only."""
    safe: Dict[str, Any] = {}
    for key, value in attrs.items():
        if isinstance(value, _ALLOWED_ATTR_TYPES):
            safe[key] = value
        elif isinstance(value, str) and len(value) <= 64 and key in settings.TRACE_STRING_ATTRS:
            safe[key] = value
    return safe


@dataclass
class Span:
    name: str
    start_ms: float
    duration_ms: float = 0.0
    status: str = "ok"
    attrs: Dict[str, Any] = field(default_factory=dict)

    @property
    def slow(self) -> bool:
        budget = settings.LATENCY_BUDGETS_MS.get(self.name)
        return budget is not None and self.duration_ms > budget


@dataclass
class Trace:
    route: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = field(default_factory=time.time)
    _t0: float = field(default_factory=time.perf_counter)
    spans: List[Span] = field(default_factory=list)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0

    def set(self, **attrs: Any) -> None:
        self.attrs.update(_safe_attrs(attrs))

    def stage_totals(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for s in self.spans:
            totals[s.name] = totals.get(s.name, 0.0) + s.duration_ms
        return totals

    def server_timing_header(self) -> str:
        """W3C Server-Timing value; visible in browser devtools without UI changes."""
        parts = [f"{name.replace('.', '_')};dur={dur:.1f}" for name, dur in self.stage_totals().items()]
        parts.append(f"total;dur={self.elapsed_ms():.1f}")
        return ", ".join(parts)

    def summary(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "total_ms": round(self.elapsed_ms(), 1),
            "stages_ms": {k: round(v, 1) for k, v in self.stage_totals().items()},
            "slow_stages": sorted({s.name for s in self.spans if s.slow}),
        }


_current: contextvars.ContextVar[Optional[Trace]] = contextvars.ContextVar("zeroday_trace", default=None)


def current_trace() -> Optional[Trace]:
    return _current.get()


@contextmanager
def start_trace(route: str, request_id: Optional[str] = None) -> Iterator[Trace]:
    trace = Trace(route=route, request_id=request_id or str(uuid.uuid4()))
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Span]:
    """Times a block and attaches it to the active trace (no-op without one)."""
    trace = current_trace()
    start = time.perf_counter()
    s = Span(name=name, start_ms=trace.elapsed_ms() if trace else 0.0, attrs=_safe_attrs(attrs))
    try:
        yield s
    except Exception:
        s.status = "error"
        raise
    finally:
        s.duration_ms = (time.perf_counter() - start) * 1000.0
        if trace is not None:
            trace.spans.append(s)
            if settings.TRACE_LOG_SPANS:
                logger.info(json.dumps({
                    "request_id": trace.request_id,
                    "span": s.name,
                    "duration_ms": round(s.duration_ms, 2),
                    "status": s.status,
                    "slow": s.slow,
                    **s.attrs,
                }))


def add_span_attrs(s: Span, **attrs: Any) -> None:
    s.attrs.update(_safe_attrs(attrs))


def traced_node(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wraps a LangGraph node so each execution becomes a `node.<name>` span."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with span(f"node.{name}"):
                return fn(*args, **kwargs)
        return wrapper
    return decorator
