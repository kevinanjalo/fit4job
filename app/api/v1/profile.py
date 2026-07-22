"""User profile endpoints: saved CVs (PDF upload, list, download, delete)
and job applications."""
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.core import audit
from app.core.security import get_current_user
from app.services import application_service, cv_service, resume_parser

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/cvs")
async def upload_cv(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files can be saved as CVs")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    text = resume_parser.extract_text(file.filename, content)
    record = cv_service.save_cv(user["sub"], file.filename, content, text)
    audit.record(user["sub"], "cv.upload", record["cv_id"])
    return record


@router.get("/cvs")
def my_cvs(user: dict = Depends(get_current_user)):
    return cv_service.list_cvs(user["sub"])


@router.get("/cvs/{cv_id}/text")
def cv_text(cv_id: str, user: dict = Depends(get_current_user)):
    """Return a saved CV's extracted text (plus detected skills) so tools can
    reuse it without re-uploading the file."""
    cv = cv_service.get_cv(cv_id)
    if cv is None or (cv["owner"] != user["sub"] and user.get("role") != "admin"):
        raise HTTPException(status_code=404, detail="CV not found")
    text = cv.get("text", "")
    parsed = resume_parser.parse_resume(text) if text else {}
    return {"cv_id": cv_id, "filename": cv["filename"], "text": text,
            "detected_skills": parsed.get("detected_skills", [])}


@router.get("/cvs/{cv_id}/download")
def download_cv(cv_id: str, user: dict = Depends(get_current_user)):
    cv = cv_service.get_cv(cv_id)
    if cv is None or (cv["owner"] != user["sub"] and user.get("role") != "admin"):
        raise HTTPException(status_code=404, detail="CV not found")
    path = Path(cv["path"])
    if not path.exists():
        raise HTTPException(status_code=410, detail="CV file is no longer on disk")
    return FileResponse(path, media_type="application/pdf", filename=cv["filename"])


@router.delete("/cvs/{cv_id}")
def delete_cv(cv_id: str, user: dict = Depends(get_current_user)):
    if not cv_service.delete_cv(cv_id, user["sub"]):
        raise HTTPException(status_code=404, detail="CV not found")
    return {"detail": "CV deleted"}


class ApplyRequest(BaseModel):
    job_id: str
    cv_id: str | None = None
    note: str = ""


@router.post("/apply")
def apply(payload: ApplyRequest, user: dict = Depends(get_current_user)):
    if payload.cv_id:
        cv = cv_service.get_cv(payload.cv_id)
        if cv is None or cv["owner"] != user["sub"]:
            raise HTTPException(status_code=404, detail="Selected CV not found")
    try:
        record = application_service.apply(user["sub"], user.get("name", user["sub"]),
                                           payload.job_id, payload.cv_id, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit.record(user["sub"], "job.apply", payload.job_id)
    return record


@router.get("/applications")
def my_applications(user: dict = Depends(get_current_user)):
    return application_service.list_for_user(user["sub"])
