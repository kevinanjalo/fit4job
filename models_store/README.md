# Model Artifacts

Place your trained research artifacts here. They are loaded automatically at
application startup; no code changes are required.

- sbert/                Fine-tuned SentenceTransformer directory
                        (save with model.save("models_store/sbert")).
                        If absent, the base all-MiniLM-L6-v2 model is used;
                        if sentence-transformers is not installed, a
                        deterministic fallback encoder keeps the app running.
- pca_model.pkl         Fitted scikit-learn PCA object (384 to 128 dims),
                        saved with pickle. Optional.
- faiss_hnsw.index      Persisted FAISS index, written by
                        Admin > RAG / AI pipeline > Rebuild vector index.

After adding or replacing artifacts, restart the server and click
"Rebuild vector index" in the admin dashboard (or POST
/api/v1/admin/pipeline/rebuild-index).

Your existing RAG pipeline can replace app/services/rag_service.py as long as
it exposes generate_interview_questions, generate_resume_feedback and
career_recommendation with the same signatures.
