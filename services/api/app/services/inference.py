import time
from typing import Any, Dict, Optional

import ollama

from services.api.app.config.settings import settings

_NS_PER_MS = 1_000_000


def _ms(value: Optional[int]) -> float:
    return round((value or 0) / _NS_PER_MS, 2)


class InferenceClient:
    """Local Ollama inference. Talks only to OLLAMA_BASE_URL (127.0.0.1 by default)."""

    def __init__(self, host: Optional[str] = None):
        self._client = ollama.Client(host=host or settings.OLLAMA_BASE_URL)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self.generate_with_meta(prompt, system_prompt)["response"]

    def generate_with_meta(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generates a response plus Ollama's own timing breakdown (all in ms)."""
        response = self._client.generate(
            model=settings.OLLAMA_MODEL,
            prompt=prompt,
            system=system_prompt or None,
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={
                "temperature": settings.LLM_TEMPERATURE,
                "seed": settings.LLM_SEED,
                "num_ctx": settings.LLM_CONTEXT_WINDOW,
                "num_predict": max_tokens or settings.LLM_MAX_TOKENS,
            },
        )
        prompt_tokens = response.get("prompt_eval_count") or 0
        completion_tokens = response.get("eval_count") or 0
        eval_ms = _ms(response.get("eval_duration"))
        return {
            "response": (response.get("response") or "").strip(),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "model_total_ms": _ms(response.get("total_duration")),
            "load_ms": _ms(response.get("load_duration")),
            "prompt_eval_ms": _ms(response.get("prompt_eval_duration")),
            "eval_ms": eval_ms,
            "tokens_per_s": round(completion_tokens / (eval_ms / 1000.0), 2) if eval_ms else 0.0,
        }

    def warmup(self) -> Dict[str, Any]:
        """Loads the model into memory so the first user question skips cold-start."""
        started = time.perf_counter()
        response = self._client.generate(
            model=settings.OLLAMA_MODEL,
            prompt="",
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            # Same num_ctx as real requests, otherwise Ollama reloads the model on the first question.
            options={"num_ctx": settings.LLM_CONTEXT_WINDOW},
        )
        return {
            "wall_ms": round((time.perf_counter() - started) * 1000, 1),
            "load_ms": _ms(response.get("load_duration")),
        }

    def status(self) -> Dict[str, Any]:
        """Reports whether the local runtime is reachable and the model resident."""
        try:
            running = self._client.ps()
        except Exception as e:
            return {"reachable": False, "error": type(e).__name__}
        models = [m for m in running.get("models", []) if m.get("model") == settings.OLLAMA_MODEL]
        loaded = models[0] if models else None
        return {
            "reachable": True,
            "model_loaded": loaded is not None,
            "model_vram_bytes": loaded.get("size_vram") if loaded else None,
            "model_size_bytes": loaded.get("size") if loaded else None,
        }


class MockInferenceClient:
    """Mock client for unit tests to avoid needing Ollama running."""

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Simulate legal doc classification
        if "classify" in prompt.lower() or "category" in prompt.lower():
            # Return non_legal if specifically mentioning apples or weather
            if "apples" in prompt.lower() or "weather" in prompt.lower():
                return "non_legal"
            # Otherwise, if it looks like a legal doc, return rental
            if any(word in prompt.lower() for word in ["agreement", "lease", "contract", "rental"]):
                return "rental"
            return "non_legal"

        return "MOCK_RESPONSE: This is a simulated response for testing purposes."


# Singleton instance
inference_client = InferenceClient()
