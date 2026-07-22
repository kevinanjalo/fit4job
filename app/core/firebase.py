"""Firestore client initialisation.

Degrades gracefully: if the service account key file is not present, an
in-memory store is used so the platform remains fully runnable locally.
"""
import os
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_db = None
_memory_store: dict = {}


def init_firebase():
    global _db
    settings = get_settings()
    path = settings.firebase_credentials_path
    if not os.path.exists(path):
        logger.warning("Firebase credentials not found at %s. Using in-memory store.", path)
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred = credentials.Certificate(path)
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
        _db = firestore.client()
        logger.info("Firestore connected: project=%s", settings.firebase_project_id)
    except Exception as exc:
        logger.error("Firebase init failed: %s. Falling back to memory store.", exc)
        _db = None
    return _db


def get_db():
    return _db


class MemoryCollection:
    """Minimal Firestore-like collection backed by a dict (local fallback)."""

    def __init__(self, name: str):
        self._store = _memory_store.setdefault(name, {})

    def set(self, doc_id: str, data: dict):
        self._store[doc_id] = dict(data)

    def get(self, doc_id: str):
        return self._store.get(doc_id)

    def delete(self, doc_id: str):
        self._store.pop(doc_id, None)

    def all(self):
        return dict(self._store)


class FirestoreCollection:
    def __init__(self, name: str):
        self._col = _db.collection(name)

    def set(self, doc_id: str, data: dict):
        self._col.document(doc_id).set(data)

    def get(self, doc_id: str):
        snap = self._col.document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def delete(self, doc_id: str):
        self._col.document(doc_id).delete()

    def all(self):
        return {d.id: d.to_dict() for d in self._col.stream()}


def collection(name: str):
    """Return a uniform collection wrapper over Firestore or memory."""
    if _db is not None:
        return FirestoreCollection(name)
    return MemoryCollection(name)
