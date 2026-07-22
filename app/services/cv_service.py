"""Saved CV management: users can upload PDF resumes, list them, and attach
them to job applications. Files live in uploads_store/cvs/, metadata in the
"cvs" collection (Firestore or in-memory fallback)."""
import time
import uuid
from pathlib import Path
from app.core import firebase

CV_DIR = Path("uploads_store/cvs")


def save_cv(user_email: str, filename: str, content: bytes, extracted_text: str) -> dict:
    CV_DIR.mkdir(parents=True, exist_ok=True)
    cv_id = uuid.uuid4().hex[:12]
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ") or "resume.pdf"
    path = CV_DIR / f"{cv_id}_{safe_name}"
    path.write_bytes(content)
    record = {
        "cv_id": cv_id,
        "owner": user_email,
        "filename": safe_name,
        "path": str(path),
        "text": extracted_text[:20000],
        "size_kb": round(len(content) / 1024, 1),
        "uploaded_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    firebase.collection("cvs").set(cv_id, record)
    return {k: v for k, v in record.items() if k != "text"}


def list_cvs(user_email: str) -> list:
    return sorted(
        [{k: v for k, v in c.items() if k != "text"}
         for c in firebase.collection("cvs").all().values() if c.get("owner") == user_email],
        key=lambda c: c.get("uploaded_at", ""), reverse=True)


def get_cv(cv_id: str) -> dict | None:
    return firebase.collection("cvs").get(cv_id)


def delete_cv(cv_id: str, user_email: str) -> bool:
    cv = get_cv(cv_id)
    if cv is None or cv.get("owner") != user_email:
        return False
    try:
        Path(cv["path"]).unlink(missing_ok=True)
    except Exception:
        pass
    firebase.collection("cvs").delete(cv_id)
    return True
