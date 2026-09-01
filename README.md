# Fit4Job

A semantically-aware IT job matching platform for Sri Lankan IT professionals,
implementing the architecture from the Fit4Job research proposal: SBERT
sentence embeddings, PCA dimensionality reduction (384 to 128 dimensions),
FAISS HNSW approximate nearest-neighbour retrieval, hybrid scoring
(70 percent semantic cosine similarity plus 30 percent taxonomy-expanded
skill overlap) and Retrieval-Augmented Generation for personalised career
support.

## Features

### Job seekers

- Semantic job matching: resume against the full job catalogue with per-job
  semantic, skill and final scores plus matched and missing skills.
- Semantic search: describe a role in plain language.
- CV upload and parsing: PDF, DOCX and TXT extraction with section detection,
  contact extraction and skill recognition.
- Saved CVs: store resumes as PDF in a personal profile and attach one when
  applying for a job.
- Job applications: apply with one click and track status from the profile.
- Skill gap analysis against a specific job, with a coverage score, a
  prioritised "learn these first" list and direct links to the roadmap topic
  that teaches each missing skill.
- Interactive skill roadmaps: 75 domain roadmaps rendered as branching trees,
  grouped by field, with a side panel that explains any topic on click.
- RAG-powered interview question generation directly from a job description.
- RAG-powered resume improvement feedback and career path recommendations.
- Job browsing with a sticky semantic search bar, sidebar filters and
  paginated results; all job cards and detail pages render from shared
  reusable templates, not per-job pages.

### Organizations

- Organization accounts (role "organization") sign up at /organization-signup.
- Post, edit and delete their own job listings (owner-scoped).
- Review applications submitted to their jobs, download applicant CVs, and
  update application status (submitted, reviewed, shortlisted, rejected).
- Role-based access control ensures an organization can only see and modify
  its own jobs and the applications to them.

### Administrators

- Job management (create, edit, delete; CSV-backed catalogue with reload).
- User management with role-based access control (user, organization and
  admin roles; activate, deactivate, promote and demote).
- Applications overview across the whole platform with status control.
- Skill taxonomy management: hierarchical relationships with overlapping
  branches, skill implication (React implies JavaScript) and alias matching.
- Roadmap JSON editing.
- RAG knowledge-base management: add Markdown documents, upload PDFs for
  automatic text extraction, and re-index.
- AI pipeline management: vector index rebuild and model artifact hot-swap
  through models_store/ (retraining hook).
- Analytics, system monitoring, application logs, audit logs.
- Configuration view and live hybrid-weight tuning.
- Data backups and maintenance tools.

### Authentication

Email and password sign-in with bcrypt hashing and JWT sessions, plus Google
Sign-In through Firebase Authentication. Google ID tokens are always verified
server side with the Firebase Admin SDK before a session is issued.

## Project structure

    fit4job/
      run.py                          Entry point
      requirements.txt
      .env / .env.example             Configuration (never commit .env)
      serviceAccountKey.json          Firebase service account (never commit)
      .gitignore
      README.md
      setup.md                        Full setup guide

      app/
        main.py                       FastAPI app factory and page routes
        config.py                     Pydantic settings loaded from .env
        core/                         Cross-cutting concerns
          logging.py                  Rotating file and console logging
          security.py                 Bcrypt hashing, JWT, RBAC dependencies
          firebase.py                 Firestore client with in-memory fallback
          audit.py                    Audit log service
        models/
          schemas.py                  Pydantic request and response models
        services/                     Business logic, one module per feature
          embedding_service.py        SBERT plus PCA loading with fallback
          faiss_service.py            FAISS HNSW index with NumPy fallback
          matching_service.py         Hybrid scoring engine
          taxonomy_service.py         Hierarchical skill graph with aliases
          job_service.py              CSV-backed job repository (owner-scoped)
          resume_parser.py            PDF, DOCX and TXT parsing
          cv_service.py               Saved CV storage and retrieval
          application_service.py      Job applications and status workflow
          skill_gap_service.py        Gap analysis and roadmap linkage
          rag_service.py              Retrieve, prompt, generate (Gemini)
          user_service.py             Accounts in Firestore
          analytics_service.py        Usage and system metrics
          backup_service.py           Data backups
        api/v1/                       Versioned REST API
          auth.py                     Register, login, Google sign-in
          jobs.py                     Public job listing and detail
          matching.py                 Matching, search, RAG, roadmaps
          profile.py                  Saved CVs and applications
          organization.py             Organization jobs and applications
          admin/routes.py             Administrative endpoints

      templates/                      Jinja2 pages (shared base, reusable blocks)
        base.html                     Layout, navigation, role-aware links
        index.html                    Landing page
        jobs.html                     Job search, filters, pagination
        job_detail.html               Job page, apply, interview prep, gap
        dashboard.html                Career tools
        roadmaps.html                 Interactive roadmap tree explorer
        profile.html                  Saved CVs and application tracking
        login.html                    Email and Google sign-in
        organization.html             Organization dashboard
        organization_signup.html      Organization registration
        admin/dashboard.html          Administrative dashboard

      static/
        css/main.css                  Design system and component styles
        js/api.js                     API client and shared UI components
        js/firebase-config.js         Public Firebase web config (Google auth)

      data/
        jobs.csv                      Job catalogue (owner column per job)
        skill_taxonomy.json           Skill graph: parents, children, implies
        roadmap_categories.json       Roadmap grouping by field
        cv/                           Resumes used by the evaluation notebook
        knowledge_base/               RAG corpus (Markdown)
        roadmaps/                     Stage-based roadmaps for career tools
        roadmap_graphs/               Node graphs for the roadmap tree view

      notebooks/
        Data_Collection.ipynb         Job posting scraping
        Data_Cleaning.ipynb           Dataset preparation
        Model_Development.ipynb       SBERT, PCA and FAISS training
        RAG_Evaluation.ipynb          RAGAS evaluation of the RAG tools

      models_store/                   Drop-in location for trained artifacts
      evaluation_results/             Excel output from RAG_Evaluation.ipynb
      uploads_store/                  Saved CV files
      logs/                           Rotating application logs
      tests/                          API smoke tests (pytest)

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
reproduced book text; extend the corpus with your own Markdown documents or
PDF uploads from the admin dashboard.

## Quick start

See setup.md for the full guide. Short version:

    python -m venv venv
    source venv/bin/activate        (Windows: venv\Scripts\activate)
    pip install -r requirements.txt
    python run.py

Open http://localhost:8000. Default admin: admin@fit4job.lk / admin123.

## API

Interactive documentation is generated automatically at /docs and /redoc.
All endpoints are under /api/v1.

| Prefix | Purpose | Access |
|---|---|---|
| /api/v1/auth | Registration, login, Google sign-in | Public |
| /api/v1/jobs | Job listing and detail | Public |
| /api/v1/match, /search, /skill-gap, /roadmap | Matching and career tools | Public |
| /api/v1/interview-prep, /resume-feedback, /career-advice | RAG tools | Public |
| /api/v1/profile | Saved CVs and applications | Signed-in user |
| /api/v1/org | Organization jobs and applications | Organization role |
| /api/v1/admin | Platform administration | Admin role |

Protected endpoints require a JWT sent as a Bearer token or the httponly
access_token cookie.

## Evaluation

### Retrieval quality

The matching service exposes semantic, skill and final scores per result, so
Precision@K, MRR and NDCG@10 can be computed against labelled CV-job pairs as
described in the research proposal. The baseline comparison (TF-IDF) can be
reproduced by swapping the encoder in embedding_service.py.

### RAG quality

notebooks/RAG_Evaluation.ipynb evaluates the Resume Feedback and Career Advice
tools with the RAGAS framework. It rebuilds the production RAG pipeline with
instrumentation so retrieved contexts are captured alongside answers, runs
both tools over the resumes in data/cv/, and scores each sample on
faithfulness, answer relevancy and context utilisation using Gemini as the
judge model. Results are written to a formatted Excel workbook in
evaluation_results/ with per-resume scores, per-tool aggregates and an overall
system score.

Run it after installing the evaluation dependencies:

    pip install "ragas>=0.2.0" "langchain-google-genai>=2.0.0" datasets openpyxl XlsxWriter

## Security notes

- Rotate the Gemini API key and Firebase service account key before
  deployment; both were exchanged in plain text during handover.
- Replace SECRET_KEY and the default admin password.
- .env and serviceAccountKey.json are gitignored; keep them out of version
  control.
- static/js/firebase-config.js holds the public Firebase web config, which is
  safe in the browser and separate from the private service account key.
