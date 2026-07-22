# Fit4Job Setup Guide

This guide takes you from a clean machine to a running Fit4Job instance.

## 1. Prerequisites

- Python 3.10 or newer (3.11 recommended)
- pip
- Approximately 2 GB of free disk space if installing the full ML stack

## 2. Create and activate a virtual environment

Windows (PowerShell):

    cd fit4job
    python -m venv venv
    venv\Scripts\Activate.ps1

Windows (Command Prompt):

    cd fit4job
    python -m venv venv
    venv\Scripts\activate.bat

Linux / macOS:

    cd fit4job
    python3 -m venv venv
    source venv/bin/activate

## 3. Install dependencies

Full installation (recommended, includes SBERT and FAISS):

    pip install --upgrade pip
    pip install -r requirements.txt

Minimal installation (if the ML packages fail to install on your machine, the
platform still runs with built-in fallbacks):

    pip install fastapi "uvicorn[standard]" jinja2 python-multipart pydantic pydantic-settings python-dotenv numpy pandas bcrypt PyJWT pdfplumber python-docx firebase-admin google-generativeai

## 4. Configure the environment

1. The project ships with a working .env file. Review it before first run.
2. GEMINI_API_KEY powers the RAG generation features. Without it, offline
   template generation is used.
3. FIREBASE_CREDENTIALS_PATH points to serviceAccountKey.json in the project
   root, which connects to Firestore project fit4job-b87dc (database
   location nam5, database id (default)). If the file is removed, the
   platform automatically uses an in-memory store for local development.
4. SECRET_KEY must be replaced with a long random string before any
   deployment. Generate one with:

       python -c "import secrets; print(secrets.token_hex(32))"

Security note: because the Gemini API key and the Firebase service account
key were shared in plain text during project handover, treat them as exposed.
Rotate the Gemini key in Google AI Studio and generate a new service account
key in the Firebase console, then update .env and serviceAccountKey.json.
Never commit .env or serviceAccountKey.json to version control; both are
already listed in .gitignore.

## 5. Integrate your trained models (optional but recommended)

Copy your research artifacts into models_store/:

- models_store/sbert/          your fine-tuned SentenceTransformer directory
- models_store/pca_model.pkl   pickled scikit-learn PCA (384 to 128 dims)
- models_store/faiss_hnsw.index persisted FAISS index (optional; the app can
  rebuild it from the job catalogue)

They are detected and loaded automatically at startup. See
models_store/README.md for details.

## 6. Run the application

    python run.py

Then open:

- http://localhost:8000            landing page
- http://localhost:8000/jobs       job listings and semantic search
- http://localhost:8000/dashboard  career tools (matching, gap analysis, RAG)
- http://localhost:8000/admin      admin dashboard
- http://localhost:8000/docs       interactive API documentation (Swagger)

Default administrator account (change in .env before deployment):

- Email: admin@fit4job.lk
- Password: admin123

## 7. Run the test suite

    pytest tests/ -v

## 8. First-run checklist

1. Sign in as the administrator and open the Admin dashboard.
2. In RAG / AI pipeline, click "Rebuild vector index" so search reflects the
   loaded models.
3. In Configuration, confirm gemini_configured is true if you expect live
   Gemini generation.
4. Create a normal user account from the Sign in page and verify role-based
   access control by attempting to open /admin endpoints.

## 9. Production deployment notes

- Run behind a process manager: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
- Terminate TLS at a reverse proxy (Nginx or a cloud load balancer) and set
  cookies to Secure.
- Replace the default admin password and SECRET_KEY.
- Schedule regular data backups (Admin > Backups or POST /api/v1/admin/backups).

## 10. Troubleshooting

- faiss-cpu or sentence-transformers fails to install: use the minimal
  installation; the app logs which fallback is active.
- Firestore connection errors: verify serviceAccountKey.json is valid and the
  machine's clock is correct; the app falls back to the in-memory store and
  logs a warning rather than crashing.
- Gemini quota or auth errors: the RAG endpoints automatically fall back to
  offline generation and record the reason in logs/fit4job.log.
