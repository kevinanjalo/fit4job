"""Central application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Fit4Job"
    app_env: str = "development"
    secret_key: str = "insecure-development-key"
    access_token_expire_minutes: int = 120

    # Gemini free tier allows a limited number of requests per day per project.
    # Extra keys from other projects extend that: rag_service falls through to
    # the next one when a key is exhausted or cannot serve the model.
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""
    gemini_api_key_3: str = ""
    gemini_api_key_4: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # Newer projects cannot serve gemini-2.5-flash and older ones cannot serve
    # gemini-3.6-flash, so each key falls back to whichever model it can reach.
    gemini_model_fallbacks: str = "gemini-2.5-flash,gemini-flash-latest"

    @property
    def gemini_models(self) -> list[str]:
        """Preferred model first, then fallbacks, de-duplicated."""
        names = [self.gemini_model, *self.gemini_model_fallbacks.split(",")]
        seen, out = set(), []
        for name in (n.strip() for n in names):
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    @property
    def gemini_api_keys(self) -> list[str]:
        """Every configured Gemini key, in fall-back order, de-duplicated."""
        keys = [self.gemini_api_key, self.gemini_api_key_2,
                self.gemini_api_key_3, self.gemini_api_key_4]
        seen, out = set(), []
        for key in (k.strip() for k in keys):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
        return out

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
