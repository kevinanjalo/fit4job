"""Job applications: users apply to jobs (optionally attaching a saved CV);
administrators review all applications and update their status."""
import time
import uuid
from app.core import firebase
from app.services.job_service import job_service

STATUSES = ("submitted", "reviewed", "shortlisted", "rejected")


def apply(user_email: str, user_name: str, job_id: str, cv_id: str | None, note: str = "") -> dict:
    job = job_service.get(job_id)
    if job is None:
        raise ValueError("Job not found")
    for a in firebase.collection("applications").all().values():
        if a.get("applicant") == user_email and a.get("job_id") == job_id:
            raise ValueError("You have already applied for this job")
    app_id = uuid.uuid4().hex[:12]
    record = {
        "application_id": app_id,
        "applicant": user_email,
        "applicant_name": user_name,
        "job_id": job_id,
        "job_title": job.title,
        "company": job.company,
        "cv_id": cv_id,
        "note": note[:1000],
        "status": "submitted",
        "applied_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    firebase.collection("applications").set(app_id, record)
    return record


def list_for_user(user_email: str) -> list:
    return sorted([a for a in firebase.collection("applications").all().values()
                   if a.get("applicant") == user_email],
                  key=lambda a: a.get("applied_at", ""), reverse=True)


def list_for_owner(owner_email: str) -> list:
    """All applications submitted to jobs owned by this organization."""
    owned = {j.job_id for j in job_service.list_by_owner(owner_email)}
    return sorted([a for a in firebase.collection("applications").all().values()
                   if a.get("job_id") in owned],
                  key=lambda a: a.get("applied_at", ""), reverse=True)


def list_all() -> list:
    return sorted(firebase.collection("applications").all().values(),
                  key=lambda a: a.get("applied_at", ""), reverse=True)


def set_status(app_id: str, status: str) -> bool:
    if status not in STATUSES:
        return False
    col = firebase.collection("applications")
    record = col.get(app_id)
    if record is None:
        return False
    record["status"] = status
    col.set(app_id, record)
    return True


def applied_job_ids(user_email: str) -> set:
    return {a["job_id"] for a in list_for_user(user_email)}
