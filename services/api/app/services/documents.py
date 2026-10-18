import hashlib
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional

from services.api.app.config.settings import settings
from services.api.app.observability.tracing import add_span_attrs, span
from services.api.app.services.chunking import chunking_service
from services.api.app.services.ingestion import ingestion_service
from services.api.app.services.retrieval import retrieval_service


@dataclass
class DocumentRecord:
    doc_key: str
    path: str
    text: str
    chunks: List[str] = field(default_factory=list)
    category: Optional[str] = None


class DocumentRegistry:
    """In-memory LRU of parsed documents keyed by content SHA-256.

    Extraction, chunking and indexing run once per document instead of on
    every question. Records live only in process memory.
    """

    def __init__(self, capacity: Optional[int] = None):
        self.capacity = capacity or settings.DOC_CACHE_SIZE
        self._records: "OrderedDict[str, DocumentRecord]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def content_key(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()

    def load(self, path: str) -> DocumentRecord:
        with span("ingest.hash", bytes=os.path.getsize(path)):
            key = self.content_key(path)

        with self._lock:
            record = self._records.get(key)
            if record is not None:
                self._records.move_to_end(key)
        if record is not None and retrieval_service.is_indexed(key):
            with span("ingest.cache", cache="hit", chunks=len(record.chunks)):
                return record

        with span("ingest.extract", cache="miss") as s:
            text = ingestion_service.extract_text(path)
            add_span_attrs(s, chars=len(text))
        with span("ingest.chunk") as s:
            chunks = chunking_service.chunk_text(text)
            add_span_attrs(s, chunks=len(chunks))
        with span("retrieval.index", backend=retrieval_service.backend, chunks=len(chunks)):
            retrieval_service.index_document(key, chunks)

        record = DocumentRecord(doc_key=key, path=path, text=text, chunks=chunks)
        with self._lock:
            self._records[key] = record
            while len(self._records) > self.capacity:
                evicted_key, _ = self._records.popitem(last=False)
                retrieval_service.forget(evicted_key)
        return record

    def get(self, doc_key: str) -> Optional[DocumentRecord]:
        with self._lock:
            return self._records.get(doc_key)


document_registry = DocumentRegistry()
