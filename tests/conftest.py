"""Test isolation. Runs before the app is imported, so settings pick it up.

Without this the tests register accounts in the live Firestore project (and
fail on the second run because the accounts already exist) and write
documents into the real knowledge base and its vector store."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="fit4job-tests-"))
_kb = _tmp / "knowledge_base"
_kb.mkdir()
(_kb / "interview_basics.md").write_text(
    "# Interview basics\n\n"
    "Prepare for a technical interview by practising data structures, explaining "
    "trade-offs out loud and reviewing the projects listed on your resume.\n",
    encoding="utf-8")

os.environ["FIREBASE_CREDENTIALS_PATH"] = str(_tmp / "no-credentials.json")
os.environ["KNOWLEDGE_BASE_DIR"] = str(_kb)
os.environ["CHROMA_PATH"] = str(_tmp / "chroma")

# Jobs are read from the real CSV but job CRUD in the tests saves to a copy.
import shutil  # noqa: E402
from app.services import job_service as _job_module  # noqa: E402

_jobs_csv = _tmp / "jobs.csv"
shutil.copy(_job_module.JOBS_CSV, _jobs_csv)
_job_module.JOBS_CSV = _jobs_csv
