"""Central application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Fit4Job"
    app_env: str = "development"
    secret_key: str = "insecure-development-key"
    access_token_expire_minutes: int = 120

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    firebase_project_id: str = ""
    firebase_credentials_path: str = "./serviceAccountKey.json"
    firestore_database_id: str = "(default)"

    sbert_model_path: str = "models_store/sbert"
    pca_model_path: str = "models_store/pca_model.pkl"
    faiss_index_path: str = "models_store/faiss_hnsw.index"
    job_embeddings_cache_path: str = "models_store/job_embeddings.npz"
    embedding_dim: int = 384
    reduced_dim: int = 128

    semantic_weight: float = 0.7
    skill_weight: float = 0.3

    admin_email: str = "admin@fit4job.lk"
    admin_password: str = "admin123"


@lru_cache
def get_settings() -> Settings:
    return Settings()
