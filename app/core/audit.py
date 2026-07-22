"""Audit log service: records administrative and security-relevant actions."""
import time
import uuid
from app.core import firebase


def record(actor: str, action: str, detail: str = "") -> None:
    entry = {
        "actor": actor,
        "action": action,
        "detail": detail,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    firebase.collection("audit_logs").set(str(uuid.uuid4()), entry)


def list_entries() -> list:
    entries = list(firebase.collection("audit_logs").all().values())
    return sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)
