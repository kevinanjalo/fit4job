"""Fit4Job application factory: mounts APIs, templates and static assets."""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import get_settings
from app.core import firebase
from app.core.logging import configure_logging, get_logger
from app.api.v1 import auth, jobs, matching, organization, profile
from app.api.v1.admin import routes as admin_routes
from app.services import user_service
from app.services.job_service import job_service

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name,
              description="Semantically-aware IT job matching platform "
                          "(SBERT + FAISS + RAG)",
              version="1.0.0")

firebase.init_firebase()
user_service.ensure_admin()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(jobs.router, prefix=API_PREFIX)
app.include_router(matching.router, prefix=API_PREFIX)
app.include_router(profile.router, prefix=API_PREFIX)
app.include_router(organization.router, prefix=API_PREFIX)
app.include_router(admin_routes.router, prefix=API_PREFIX)


def asset_version() -> str:
    """Cache-busting token for /static assets: the newest mtime under static/.

    Without it browsers keep serving a stale main.css after a style change.
    """
    try:
        return str(int(max(p.stat().st_mtime for p in Path("static").rglob("*") if p.is_file())))
    except ValueError:
        return "0"


def render(request: Request, template: str, **ctx):
    return templates.TemplateResponse(request=request, name=template,
                                      context={"app_name": settings.app_name,
                                               "asset_v": asset_version(), **ctx})


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return render(request, "index.html")


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request):
    return render(request, "jobs.html")


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(request: Request, job_id: str):
    job = job_service.get(job_id)
    return render(request, "job_detail.html", job=job, job_id=job_id)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return render(request, "dashboard.html")


@app.get("/roadmaps", response_class=HTMLResponse)
def roadmaps_page(request: Request):
    return render(request, "roadmaps.html")


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    return render(request, "profile.html")


@app.get("/organization", response_class=HTMLResponse)
def organization_page(request: Request):
    return render(request, "organization.html")


@app.get("/organization-signup", response_class=HTMLResponse)
def organization_signup_page(request: Request):
    return render(request, "organization_signup.html")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return render(request, "admin/dashboard.html")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
