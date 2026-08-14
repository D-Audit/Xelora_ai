"""
knowledge/rag.py
Retrieval-Augmented Generation, kept intentionally lightweight: a local
TF-IDF index over ingested documents (company docs, manuals, previous
reports, Excel workbooks converted to text) rather than a hosted vector
DB or an embeddings API call. This means:
  - No extra API cost or network dependency to search your own documents
  - Good enough for keyword/topic-level retrieval over a small-to-medium
    document set (hundreds to low thousands of chunks)
  - NOT semantic-embedding quality - it won't catch purely conceptual
    matches with no shared vocabulary. If retrieval quality matters more
    than simplicity, swap this for a real embedding-based vector store
    (e.g. pgvector, Chroma) later - the KnowledgeBase interface below
    (add_document/search) is designed to be a drop-in replacement point.

Persisted as a single file per user under knowledge/data/ so it survives
restarts without needing its own database table.
"""

import contextvars
import os
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_CURRENT_USER_ID = contextvars.ContextVar("current_user_id_for_kb", default=None)


def bind_user_context(user_id):
    _CURRENT_USER_ID.set(user_id)


def current_user_id():
    return _CURRENT_USER_ID.get()


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list:
    """Splits long text into overlapping chunks so retrieval can point to
    a specific passage instead of matching (or missing) an entire document."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]


class KnowledgeBase:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.path = os.path.join(DATA_DIR, f"user_{user_id}.pkl")
        self.chunks = []       # list of {"doc_id": str, "text": str}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                self.chunks = pickle.load(f)

    def _save(self):
        with open(self.path, "wb") as f:
            pickle.dump(self.chunks, f)

    def add_document(self, doc_id: str, text: str) -> int:
        """Chunks and adds a document's text to the index. Returns the
        number of chunks added."""
        new_chunks = [{"doc_id": doc_id, "text": chunk} for chunk in _chunk_text(text)]
        self.chunks.extend(new_chunks)
        self._save()
        return len(new_chunks)

    def remove_document(self, doc_id: str) -> int:
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["doc_id"] != doc_id]
        self._save()
        return before - len(self.chunks)

    def search(self, query: str, top_k: int = 5) -> list:
        """Returns the top_k most relevant chunks as
        [{"doc_id", "text", "score"}, ...], highest score first."""
        if not self.chunks:
            return []

        corpus = [c["text"] for c in self.chunks] + [query]
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(corpus)

        query_vector = matrix[-1]
        doc_vectors = matrix[:-1]
        scores = cosine_similarity(query_vector, doc_vectors).flatten()

        ranked_indices = scores.argsort()[::-1][:top_k]
        return [
            {"doc_id": self.chunks[i]["doc_id"], "text": self.chunks[i]["text"], "score": float(scores[i])}
            for i in ranked_indices if scores[i] > 0
        ]

    def list_documents(self) -> list:
        return sorted(set(c["doc_id"] for c in self.chunks))
