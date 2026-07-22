"""Administrative API: jobs, users, taxonomy, roadmaps, RAG KB, analytics,
audit logs, configuration, backups and maintenance. All routes require the
admin role (role-based access control)."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from app.config import get_settings
from app.core import audit
from app.core.security import require_admin
from app.models.schemas import JobCreate, TaxonomyNode
from app.services import analytics_service, application_service, backup_service, cv_service, resume_parser, skill_gap_service, user_service
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.rag_service import knowledge_base
from app.services.taxonomy_service import taxonomy_service
from pathlib import Path

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ----- Jobs -----
@router.post("/jobs")
def create_job(payload: JobCreate, admin=Depends(require_admin)):
    job = job_service.create(payload)
    matching_service.rebuild_index()
    audit.record(admin["sub"], "job.create", job.job_id)
    return job.model_dump()


@router.put("/jobs/{job_id}")
def update_job(job_id: str, payload: JobCreate, admin=Depends(require_admin)):
    job = job_service.update(job_id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    matching_service.rebuild_index()
    audit.record(admin["sub"], "job.update", job_id)
    return job.model_dump()


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, admin=Depends(require_admin)):
    if not job_service.delete(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    matching_service.rebuild_index()
    audit.record(admin["sub"], "job.delete", job_id)
    return {"detail": "Deleted"}


# ----- Users -----
@router.get("/users")
def list_users():
    return user_service.list_users()


class UserAction(BaseModel):
    email: str
    active: bool | None = None
    role: str | None = None


@router.post("/users/update")
def update_user(payload: UserAction, admin=Depends(require_admin)):
    ok = True
    if payload.active is not None:
        ok = user_service.set_active(payload.email, payload.active) and ok
    if payload.role is not None:
        ok = user_service.set_role(payload.email, payload.role) and ok
    if not ok:
        raise HTTPException(status_code=404, detail="User not found or invalid role")
    audit.record(admin["sub"], "user.update", payload.email)
    return {"detail": "Updated"}


# ----- Taxonomy -----
@router.get("/taxonomy")
def get_taxonomy():
    return taxonomy_service.all()


@router.post("/taxonomy/{name}")
def upsert_taxonomy(name: str, node: TaxonomyNode, admin=Depends(require_admin)):
    taxonomy_service.upsert(name, node.model_dump())
    audit.record(admin["sub"], "taxonomy.upsert", name)
    return {"detail": "Saved"}


@router.delete("/taxonomy/{name}")
def delete_taxonomy(name: str, admin=Depends(require_admin)):
    taxonomy_service.delete(name)
    audit.record(admin["sub"], "taxonomy.delete", name)
    return {"detail": "Deleted"}


# ----- Roadmaps -----
@router.get("/roadmaps")
def roadmaps():
    return skill_gap_service.load_roadmaps()


@router.post("/roadmaps/{name}")
def save_roadmap(name: str, data: dict, admin=Depends(require_admin)):
    skill_gap_service.save_roadmap(name, data)
    audit.record(admin["sub"], "roadmap.save", name)
    return {"detail": "Saved"}


# ----- AI pipeline / RAG -----
@router.post("/pipeline/rebuild-index")
def rebuild_index(admin=Depends(require_admin)):
    matching_service.rebuild_index()
    matching_service.index.save()
    audit.record(admin["sub"], "pipeline.rebuild_index")
    return {"detail": "Vector index rebuilt", "items": len(matching_service.index.ids)}


@router.post("/rag/rebuild")
def rebuild_kb(admin=Depends(require_admin)):
    knowledge_base.rebuild()
    audit.record(admin["sub"], "rag.rebuild")
    return {"detail": "Knowledge base re-indexed", "chunks": len(knowledge_base.chunks)}


@router.get("/rag/documents")
def kb_documents():
    return knowledge_base.documents()


@router.post("/rag/upload-pdf")
async def upload_kb_pdf(file: UploadFile = File(...), admin=Depends(require_admin)):
    """Add a PDF document to the RAG knowledge base: extract its text,
    store it as Markdown and re-index."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted here")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    text = resume_parser.extract_text(file.filename, content)
    if len(text.strip()) < 100:
        raise HTTPException(status_code=422, detail="Could not extract readable text from this PDF")
    stem = Path(file.filename).stem
    safe = "".join(c for c in stem if c.isalnum() or c in "-_ ").strip().replace(" ", "_") or "document"
    Path("data/knowledge_base", f"{safe}.md").write_text(f"# {stem}\n\n{text}", encoding="utf-8")
    knowledge_base.rebuild()
    audit.record(admin["sub"], "rag.pdf.upload", safe)
    return {"detail": f"PDF indexed as {safe}", "characters": len(text)}


# ----- Applications -----
@router.get("/applications")
def list_applications():
    return application_service.list_all()


class StatusUpdate(BaseModel):
    application_id: str
    status: str


@router.post("/applications/status")
def set_application_status(payload: StatusUpdate, admin=Depends(require_admin)):
    if not application_service.set_status(payload.application_id, payload.status):
        raise HTTPException(status_code=400, detail="Unknown application or invalid status")
    audit.record(admin["sub"], "application.status", f"{payload.application_id}={payload.status}")
    return {"detail": "Status updated"}


class KBDocument(BaseModel):
    name: str
    content: str


@router.post("/rag/documents")
def add_kb_document(payload: KBDocument, admin=Depends(require_admin)):
    safe = "".join(c for c in payload.name if c.isalnum() or c in "-_")
    Path("data/knowledge_base", f"{safe}.md").write_text(payload.content, encoding="utf-8")
    knowledge_base.rebuild()
    audit.record(admin["sub"], "rag.document.add", safe)
    return {"detail": "Document added and indexed"}


# ----- Analytics / monitoring / logs -----
@router.get("/analytics")
def analytics():
    return analytics_service.summary()


@router.get("/system")
def system():
    return analytics_service.system_status()


@router.get("/audit-logs")
def audit_logs():
    return audit.list_entries()


@router.get("/app-logs")
def app_logs(lines: int = 100):
    path = Path("logs/fit4job.log")
    if not path.exists():
        return {"lines": []}
    content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return {"lines": content[-lines:]}


# ----- Configuration -----
@router.get("/config")
def get_config():
    s = get_settings()
    return {"app_name": s.app_name, "app_env": s.app_env,
            "semantic_weight": s.semantic_weight, "skill_weight": s.skill_weight,
            "embedding_dim": s.embedding_dim, "reduced_dim": s.reduced_dim,
            "gemini_model": s.gemini_model,
            "gemini_configured": bool(s.gemini_api_key),
            "firestore_project": s.firebase_project_id}


class Weights(BaseModel):
    semantic_weight: float
    skill_weight: float


@router.post("/config/weights")
def set_weights(payload: Weights, admin=Depends(require_admin)):
    s = get_settings()
    s.semantic_weight = payload.semantic_weight
    s.skill_weight = payload.skill_weight
    audit.record(admin["sub"], "config.weights", f"{payload.semantic_weight}/{payload.skill_weight}")
    return {"detail": "Weights updated for the running instance"}


# ----- Backups / maintenance -----
@router.post("/backups")
def create_backup(admin=Depends(require_admin)):
    path = backup_service.create_backup()
    audit.record(admin["sub"], "backup.create", path)
    return {"detail": "Backup created", "path": path}


@router.get("/backups")
def list_backups():
    return backup_service.list_backups()


@router.post("/maintenance/reload-jobs")
def reload_jobs(admin=Depends(require_admin)):
    job_service.load_csv()
    matching_service.rebuild_index()
    audit.record(admin["sub"], "maintenance.reload_jobs")
    return {"detail": "Jobs reloaded from CSV and index rebuilt"}
