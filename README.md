# Fit4Job

A semantically-aware IT job matching platform for Sri Lankan IT professionals,
implementing the architecture from the Fit4Job research proposal: SBERT
sentence embeddings, PCA dimensionality reduction (384 to 128 dimensions),
FAISS HNSW approximate nearest-neighbour retrieval, hybrid scoring
(70 percent semantic cosine similarity plus 30 percent taxonomy-expanded
skill overlap) and Retrieval-Augmented Generation for personalised career
support.

## Features

User-facing:

- Semantic job matching: resume against the full job catalogue with per-job
  semantic, skill and final scores plus matched and missing skills.
- Semantic search: describe a role in plain language.
- CV upload and parsing: PDF, DOCX and TXT extraction with section detection,
  contact extraction and skill recognition.
- Skill gap analysis against a specific job, mapped to learning roadmaps.
- Personalised learning roadmaps per domain with completed and remaining
  stages based on detected skills.
- RAG-powered interview question generation directly from a job description.
- RAG-powered resume improvement feedback and career path recommendations.
- Job browsing with keyword, location and level filters; all job cards and
  detail pages render from shared reusable templates, not per-job pages.

Organizations:

- Organization accounts (role "organization") sign up at /organization-signup.
- Post, edit and delete their own job listings (owner-scoped).
- Review applications submitted to their jobs, download applicant CVs, and
  update application status (submitted, reviewed, shortlisted, rejected).
- Role-based access control ensures an organization can only see and modify
  its own jobs and the applications to them.

Administrative:

- Job management (create, edit, delete; CSV-backed catalogue with reload).
- User management with role-based access control (user and admin roles,
  activate and deactivate, promote and demote).
- Skill taxonomy management: hierarchical relationships with overlapping
  branches and skill implication (for example React implies JavaScript).
- Roadmap JSON editing.
- RAG knowledge-base management: add Markdown documents and re-index.
- AI pipeline management: vector index rebuild and model artifact hot-swap
  through models_store/ (retraining hook).
- Analytics, system monitoring, application logs, audit logs.
- Configuration view and live hybrid-weight tuning.
- Data backups and maintenance tools.

## Architecture

    fit4job/
      run.py                     Entry point
      requirements.txt
      .env / .env.example        Configuration (never commit .env)
      serviceAccountKey.json     Firebase service account (never commit)
      setup.md                   Full setup guide
      app/
        main.py                  FastAPI app factory and page routes
        config.py                Pydantic settings
        core/                    Cross-cutting concerns
          logging.py             Rotating file and console logging
          security.py            Bcrypt hashing, JWT, RBAC dependencies
          firebase.py            Firestore client with in-memory fallback
          audit.py               Audit log service
        models/schemas.py        Pydantic request and response models
        services/                Business logic, one module per feature
          embedding_service.py   SBERT plus PCA loading with fallback
          faiss_service.py       FAISS HNSW index with NumPy fallback
          matching_service.py    Hybrid scoring engine
          taxonomy_service.py    Hierarchical skill graph
          job_service.py         CSV-backed job repository
          resume_parser.py       PDF, DOCX and TXT parsing
          skill_gap_service.py   Gap analysis and roadmaps
          rag_service.py         Retrieve, prompt, generate (Gemini)
          user_service.py        Accounts in Firestore
          analytics_service.py   Usage and system metrics
          backup_service.py      Data backups
        api/v1/                  Versioned REST API
          auth.py jobs.py matching.py admin/routes.py
      templates/                 Jinja2 pages (shared base and reusable blocks)
      static/css static/js       Design system and shared frontend components
      data/                      jobs.csv, skill_taxonomy.json, roadmaps/,
                                 knowledge_base/
      models_store/              Drop-in location for trained artifacts
      tests/                     API smoke tests (pytest)

Design principles applied: separation of concerns (API, service and data
layers), dependency inversion at integration points (embedding, index,
database and LLM all have graceful fallbacks), single reusable template per
UI concept, versioned API, role-based access control, audit logging, and
configuration through environment variables.

## Knowledge base

data/knowledge_base/ contains original summaries of widely accepted software
engineering, system design, information retrieval, resume writing, interview
preparation and career development principles, organised for retrieval. These
draw on the themes of well-known industry references but contain no
reproduced book text; extend the corpus with your own Markdown documents from
the admin dashboard.

## Quick start

See setup.md for the full guide. Short version:

    python -m venv venv
    source venv/bin/activate        (Windows: venv\Scripts\activate)
    pip install -r requirements.txt
    python run.py

Open http://localhost:8000. Default admin: admin@fit4job.lk / admin123.

## API

Interactive documentation is generated automatically at /docs and /redoc.
All endpoints are under /api/v1. Admin endpoints require a JWT with the admin
role, sent as a Bearer token or the httponly access_token cookie.

## Evaluation hooks

The matching service exposes semantic, skill and final scores per result, so
Precision@K, MRR and NDCG@10 can be computed against labelled CV-job pairs as
described in the research proposal. The baseline comparison (TF-IDF) can be
reproduced by swapping the encoder in embedding_service.py.

## Security notes

- Rotate the Gemini API key and Firebase service account key before
  deployment; both were exchanged in plain text during handover.
- Replace SECRET_KEY and the default admin password.
- .env and serviceAccountKey.json are gitignored; keep them out of version
  control.
