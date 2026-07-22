"""Smoke tests for the core API surface."""
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)
settings = get_settings()


def admin_headers():
    r = client.post("/api/v1/auth/login",
                    json={"email": settings.admin_email, "password": settings.admin_password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_jobs_list_and_detail():
    jobs = client.get("/api/v1/jobs").json()
    assert len(jobs) > 0
    job = client.get(f"/api/v1/jobs/{jobs[0]['job_id']}").json()
    assert job["title"]


def test_match_and_search():
    r = client.post("/api/v1/match", json={"resume_text": "Python Django FastAPI PostgreSQL Docker developer", "top_k": 5})
    assert r.status_code == 200 and len(r.json()) > 0
    assert 0 <= r.json()[0]["final_score"] <= 1
    s = client.post("/api/v1/search", json={"query": "backend python engineer", "top_k": 3})
    assert s.status_code == 200 and len(s.json()) > 0


def test_skill_gap_and_roadmap():
    jobs = client.get("/api/v1/jobs").json()
    r = client.post("/api/v1/skill-gap", json={"resume_text": "I know Python and SQL", "job_id": jobs[0]["job_id"]})
    assert r.status_code == 200 and "missing_skills" in r.json()
    rm = client.post("/api/v1/roadmap", json={"domain": "backend", "known_skills": ["Python"]})
    assert rm.status_code == 200 and rm.json()["stages"]


def test_auth_and_rbac():
    r = client.post("/api/v1/auth/register",
                    json={"name": "Test", "email": "test@example.com", "password": "secret1"})
    assert r.status_code == 200
    denied = client.get("/api/v1/admin/users",
                        headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert denied.status_code == 403
    allowed = client.get("/api/v1/admin/users", headers=admin_headers())
    assert allowed.status_code == 200


def test_admin_job_crud():
    h = admin_headers()
    created = client.post("/api/v1/admin/jobs", headers=h, json={
        "title": "Test Engineer", "company": "TestCo", "location": "Colombo",
        "description": "Test role", "skills": ["Python"]})
    assert created.status_code == 200
    jid = created.json()["job_id"]
    assert client.delete(f"/api/v1/admin/jobs/{jid}", headers=h).status_code == 200
