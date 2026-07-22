"""User accounts stored in Firestore (or in-memory fallback)."""
import time
import uuid
from app.config import get_settings
from app.core import firebase
from app.core.security import hash_password, verify_password


def ensure_admin():
    settings = get_settings()
    users = firebase.collection("users")
    if users.get(settings.admin_email) is None:
        users.set(settings.admin_email, {
            "user_id": str(uuid.uuid4()), "name": "Administrator",
            "email": settings.admin_email,
            "password_hash": hash_password(settings.admin_password),
            "role": "admin", "active": True,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })


def register(name: str, email: str, password: str) -> dict:
    users = firebase.collection("users")
    if users.get(email) is not None:
        raise ValueError("An account with this email already exists")
    record = {
        "user_id": str(uuid.uuid4()), "name": name, "email": email,
        "password_hash": hash_password(password), "role": "user", "active": True,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    users.set(email, record)
    return record


def find_or_create_google_user(name: str, email: str) -> dict:
    users = firebase.collection("users")
    user = users.get(email)
    if user is not None:
        return user
    record = {
        "user_id": str(uuid.uuid4()), "name": name, "email": email,
        "password_hash": None, "role": "user", "active": True,
        "auth_provider": "google",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    users.set(email, record)
    return record


def authenticate(email: str, password: str) -> dict | None:
    user = firebase.collection("users").get(email)
    if user and user.get("active", True) and verify_password(password, user["password_hash"]):
        return user
    return None


def list_users() -> list:
    return [{k: v for k, v in u.items() if k != "password_hash"}
            for u in firebase.collection("users").all().values()]


def set_active(email: str, active: bool) -> bool:
    users = firebase.collection("users")
    user = users.get(email)
    if user is None:
        return False
    user["active"] = active
    users.set(email, user)
    return True


def set_role(email: str, role: str) -> bool:
    users = firebase.collection("users")
    user = users.get(email)
    if user is None or role not in ("user", "admin"):
        return False
    user["role"] = role
    users.set(email, user)
    return True
