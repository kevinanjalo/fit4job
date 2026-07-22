"""Embedding service.

Loads the trained SBERT model and PCA reducer from models_store/ when
available. If the artifacts are absent (fresh clone), a deterministic
hashing-based fallback encoder keeps the platform functional so that the
trained models can be dropped in later without any code change.
"""
import hashlib
import os
import pickle
import numpy as np
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self):
        self.settings = get_settings()
        self.model = None
        self.pca = None
        self._load()

    def _load(self):
        path = self.settings.sbert_model_path
        try:
            from sentence_transformers import SentenceTransformer
            source = path if os.path.isdir(path) else "sentence-transformers/all-MiniLM-L6-v2"
            self.model = SentenceTransformer(source)
            logger.info("SBERT loaded from %s", source)
        except Exception as exc:
            logger.warning("SBERT unavailable (%s); using hashing fallback encoder.", exc)
        self._load_pca()

    def _load_pca(self):
        """Load the PCA reducer, supporting both pickle and joblib formats."""
        pca_path = self.settings.pca_model_path
        if not os.path.exists(pca_path):
            return
        try:
            with open(pca_path, "rb") as f:
                self.pca = pickle.load(f)
            logger.info("PCA reducer loaded (pickle) from %s", pca_path)
            return
        except Exception as pickle_exc:
            logger.info("Pickle load failed (%s); trying joblib.", pickle_exc)
        try:
            import joblib
            self.pca = joblib.load(pca_path)
            logger.info("PCA reducer loaded (joblib) from %s", pca_path)
        except Exception as exc:
            self.pca = None
            logger.warning("Failed to load PCA model with pickle and joblib: %s", exc)

    @property
    def dim(self) -> int:
        if self.pca is not None:
            return self.settings.reduced_dim
        return self.settings.embedding_dim

    def _fallback_encode(self, text: str) -> np.ndarray:
        """Deterministic bag-of-hashed-tokens embedding (development only)."""
        vec = np.zeros(self.settings.embedding_dim, dtype=np.float32)
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.settings.embedding_dim] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        if self.model is not None:
            emb = np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)
        else:
            emb = np.vstack([self._fallback_encode(t) for t in texts])
        if self.pca is not None:
            emb = np.asarray(self.pca.transform(emb), dtype=np.float32)
            norms = np.linalg.norm(emb, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            emb = emb / norms
        return emb


embedding_service = EmbeddingService()