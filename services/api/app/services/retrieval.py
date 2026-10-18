import math
import os
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from services.api.app.config.settings import settings

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "was", "be", "and", "or", "of", "in", "to", "for", "on", "by",
    "with", "what", "when", "how", "who", "does", "do", "i", "my", "me", "this", "that", "it",
    "there", "any", "can", "will", "much", "many", "about", "document", "agreement",
}
# Words that describe the question rather than its subject. They never decide
# whether the document covers a topic.
_GENERIC = {
    "mention", "say", "state", "clause", "contract", "term", "include", "allow", "explain", "tell",
    "please", "mean", "should", "would", "could", "if", "not", "no", "yes", "under", "have", "has",
    "get", "need", "happen", "where", "which", "why", "am", "we", "you", "your", "our", "us", "they",
    "their", "from", "at", "as", "all", "also", "per", "anything", "something", "section", "lease",
    "talk", "cover", "specif", "detail", "info", "information", "rule", "policy",
    # Vague evaluative words ("Is this okay?") carry no topic to look for.
    "okay", "ok", "fine", "good", "bad", "fair", "right", "wrong", "normal", "safe", "risk", "risky",
    "problem", "issue", "concern", "important", "summary", "summarize", "summarise", "key", "main",
    "point", "thing", "overall", "standard", "usual", "worry", "careful", "watch", "out",
}


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> List[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25Index:
    """Okapi BM25 over one document's chunks. Pure Python, in memory, no network."""

    def __init__(self, chunks: List[str], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(c)) for c in chunks]
        self.lengths = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.vocab = set(df)

    def mentions(self, word: str) -> bool:
        """True if the word, or a close variant (terminated/terminate), occurs anywhere."""
        stem = _stem(word.lower())
        if stem in self.vocab:
            return True
        prefix = stem[:5] if len(stem) >= 5 else stem
        return len(prefix) >= 4 and any(v.startswith(prefix) for v in self.vocab)

    def search(self, query: str, k: int) -> List[Tuple[int, float]]:
        terms = tokenize(query)
        scores = []
        for i, tf in enumerate(self.tfs):
            score = 0.0
            for t in terms:
                f = tf.get(t)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.lengths[i] / (self.avgdl or 1))
                score += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


class RetrievalService:
    """Local retrieval. BM25 by default; ChromaDB optional (RETRIEVAL_BACKEND=chroma)."""

    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or settings.RETRIEVAL_BACKEND
        self._bm25: Dict[str, BM25Index] = {}
        self.last_hits = 0
        self._collection = None
        if self.backend == "chroma":
            # Chroma ships anonymous usage telemetry enabled; turn it off before import.
            os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            client = chromadb.Client(ChromaSettings(anonymized_telemetry=False))
            self._collection = client.get_or_create_collection(name="legal_docs", metadata={"hnsw:space": "cosine"})

    def is_indexed(self, doc_id: str) -> bool:
        return doc_id in self._bm25

    def index_document(self, doc_id: str, chunks: List[str]):
        self._bm25[doc_id] = BM25Index(chunks)
        if self._collection is not None and chunks:
            self._collection.upsert(
                documents=chunks,
                ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
                metadatas=[{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))],
            )

    def coverage(self, query: str, doc_id: Optional[str]) -> Tuple[List[str], List[str]]:
        """Returns (subject words in the question, those absent from the whole document).

        Only meaningful for the BM25 backend; returns no missing words otherwise.
        """
        subject = []
        for word in _TOKEN.findall(query.lower()):
            stem = _stem(word)
            if word in _STOP or stem in _GENERIC or word in _GENERIC or word.isdigit():
                continue
            if word not in subject:
                subject.append(word)
        index = self._bm25.get(doc_id) if doc_id else None
        if index is None or self._collection is not None:
            return subject, []
        return subject, [w for w in subject if not index.mentions(w)]

    def forget(self, doc_id: str):
        self._bm25.pop(doc_id, None)
        if self._collection is not None:
            self._collection.delete(where={"doc_id": doc_id})

    def retrieve(self, query: str, doc_id: Optional[str] = None) -> List[str]:
        """Returns up to RETRIEVAL_K chunks, most relevant first."""
        k = settings.RETRIEVAL_K
        if self._collection is not None:
            results = self._collection.query(
                query_texts=[query], n_results=k, where={"doc_id": doc_id} if doc_id else None
            )
            docs = results["documents"][0] if results["documents"] else []
            self.last_hits = len(docs)
            return docs

        index = self._bm25.get(doc_id) if doc_id else None
        if index is None:
            self.last_hits = 0
            return []
        ranked = index.search(query, k)
        hits = [i for i, score in ranked if score > 0]
        self.last_hits = len(hits)
        if not hits:
            # No lexical overlap: give the model the opening of the document so it
            # can say the document is silent instead of answering from nothing.
            hits = list(range(min(k, len(index.chunks))))
        return [index.chunks[i] for i in hits]


retrieval_service = RetrievalService()
