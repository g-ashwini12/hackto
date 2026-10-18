import hashlib
import json
import os
import time
from typing import Any, Dict, Optional

from services.api.app.config.settings import settings


class ManifestService:
    """Writes a reproduction manifest for every LLM call.

    Stores a SHA-256 of the prompt (never the prompt itself) plus the
    model, decoding config and timings needed to reproduce and profile it.
    """

    def create_manifest(
        self,
        request_id: str,
        prompt: str,
        model_tag: str,
        config: Dict[str, Any],
        stage: str = "answer",
        timings: Optional[Dict[str, Any]] = None,
    ) -> str:
        manifest = {
            "request_id": request_id,
            "stage": stage,
            "timestamp": time.time(),
            "model": model_tag,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_chars": len(prompt),
            "config": config,
            "seed": settings.LLM_SEED,
            "temperature": settings.LLM_TEMPERATURE,
            "timings": timings or {},
        }

        os.makedirs(settings.MANIFEST_DIR, exist_ok=True)
        file_path = os.path.join(settings.MANIFEST_DIR, f"{request_id}-{stage}.json")
        with open(file_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return file_path


manifest_service = ManifestService()
