"""FAISS HNSW index service with a NumPy brute-force fallback."""
import os
import numpy as np
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False


class VectorIndex:
    def __init__(self, dim: int):
        self.dim = dim
        self.settings = get_settings()
        self.ids: list = []
        self._matrix = np.zeros((0, dim), dtype=np.float32)
        self.index = None
        if FAISS_AVAILABLE:
            path = self.settings.faiss_index_path
            if os.path.exists(path):
                try:
                    self.index = faiss.read_index(path)
                    logger.info("FAISS index loaded from %s", path)
                except Exception as exc:
                    logger.warning("Could not read FAISS index: %s", exc)
            if self.index is None:
                self.index = faiss.IndexHNSWFlat(dim, 32)
                self.index.hnsw.efConstruction = 200
                self.index.hnsw.efSearch = 64

    def rebuild(self, ids: list, vectors: np.ndarray):
        self.ids = list(ids)
        self._matrix = vectors.astype(np.float32)
        if FAISS_AVAILABLE:
            self.index = faiss.IndexHNSWFlat(self.dim, 32)
            self.index.hnsw.efConstruction = 200
            self.index.hnsw.efSearch = 64
            self.index.add(self._matrix)
        logger.info("Vector index rebuilt with %d items (faiss=%s)", len(ids), FAISS_AVAILABLE)

    def save(self):
        if FAISS_AVAILABLE and self.index is not None:
            faiss.write_index(self.index, self.settings.faiss_index_path)

    def search(self, query: np.ndarray, top_k: int = 10):
        if len(self.ids) == 0:
            return []
        top_k = min(top_k, len(self.ids))
        if FAISS_AVAILABLE and self.index is not None and self.index.ntotal == len(self.ids):
            dist, idx = self.index.search(query.reshape(1, -1).astype(np.float32), top_k)
            # HNSWFlat returns L2 distances over normalised vectors; convert to cosine.
            sims = 1.0 - dist[0] / 2.0
            return [(self.ids[i], float(s)) for i, s in zip(idx[0], sims) if i >= 0]
        sims = self._matrix @ query.astype(np.float32)
        order = np.argsort(-sims)[:top_k]
        return [(self.ids[i], float(sims[i])) for i in order]
