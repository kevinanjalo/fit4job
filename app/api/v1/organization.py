"""Organization endpoints: organizations post and manage their own job
listings and review applications submitted to those jobs. All routes require
the organization role (role-based access control); an organization can only
see and modify jobs it owns."""
from fastapi import APIRouter, Depends, HTTPException
from app.core import audit
from app.core.security import require_organization
from app.models.schemas import JobCreate
from app.services import application_service, cv_service
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from pydantic import BaseModel

router = APIRouter(prefix="/org", tags=["organization"], dependencies=[Depends(require_organization)])


@router.get("/jobs")
def my_jobs(org: dict = Depends(require_organization)):
    """Jobs posted by the signed-in organization, each with its application count."""
    jobs = job_service.list_by_owner(org["sub"])
    apps = application_service.list_for_owner(org["sub"])
    counts: dict = {}
    for a in apps:
        counts[a["job_id"]] = counts.get(a["job_id"], 0) + 1
    return [{**j.model_dump(), "application_count": counts.get(j.job_id, 0)} for j in jobs]


@router.post("/jobs")
def create_job(payload: JobCreate, org: dict = Depends(require_organization)):
    job = job_service.create(payload, owner=org["sub"])
    matching_service.rebuild_index()
    audit.record(org["sub"], "org.job.create", job.job_id)
    return job.model_dump()


@router.put("/jobs/{job_id}")
def update_job(job_id: str, payload: JobCreate, org: dict = Depends(require_organization)):
    if not job_service.is_owner(job_id, org["sub"]):
        raise HTTPException(status_code=403, detail="You can only edit jobs your organization posted")
    job = job_service.update(job_id, payload)
    matching_service.rebuild_index()
    audit.record(org["sub"], "org.job.update", job_id)
    return job.model_dump()


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, org: dict = Depends(require_organization)):
    if not job_service.is_owner(job_id, org["sub"]):
        raise HTTPException(status_code=403, detail="You can only delete jobs your organization posted")
    job_service.delete(job_id)
    matching_service.rebuild_index()
    audit.record(org["sub"], "org.job.delete", job_id)
    return {"detail": "Job deleted"}


@router.get("/applications")
def my_applications(org: dict = Depends(require_organization)):
    """All applications submitted to this organization's jobs."""
    return application_service.list_for_owner(org["sub"])


class StatusUpdate(BaseModel):
    application_id: str
    status: str


@router.post("/applications/status")
def set_application_status(payload: StatusUpdate, org: dict = Depends(require_organization)):
    # Ensure the application belongs to one of this organization's jobs.
    owned = {a["application_id"] for a in application_service.list_for_owner(org["sub"])}
    if payload.application_id not in owned:
        raise HTTPException(status_code=403, detail="This application is not for one of your jobs")
    if not application_service.set_status(payload.application_id, payload.status):
        raise HTTPException(status_code=400, detail="Invalid status")
    audit.record(org["sub"], "org.application.status", f"{payload.application_id}={payload.status}")
    return {"detail": "Status updated"}


@router.get("/applications/{application_id}/cv")
def download_applicant_cv(application_id: str, org: dict = Depends(require_organization)):
    """Let an organization download the CV attached to an application for one
    of its own jobs."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    apps = {a["application_id"]: a for a in application_service.list_for_owner(org["sub"])}
    app = apps.get(application_id)
    if app is None:
        raise HTTPException(status_code=403, detail="This application is not for one of your jobs")
    if not app.get("cv_id"):
        raise HTTPException(status_code=404, detail="This applicant did not attach a CV")
    cv = cv_service.get_cv(app["cv_id"])
    if cv is None or not Path(cv["path"]).exists():
        raise HTTPException(status_code=410, detail="CV file is no longer available")
    return FileResponse(cv["path"], media_type="application/pdf", filename=cv["filename"])
