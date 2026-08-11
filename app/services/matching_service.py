"""Hybrid semantic + skill-overlap job matching.

Score_Final = alpha * cosine similarity (SBERT embeddings, FAISS retrieval)
            + beta  * Jaccard similarity over taxonomy-expanded skill sets.
"""
import hashlib
import os
import numpy as np
from app.config import get_settings
from app.core.logging import get_logger
from app.models.schemas import MatchResult
from app.services.embedding_service import embedding_service
from app.services.faiss_service import VectorIndex
from app.services.job_service import job_service
from app.services.taxonomy_service import taxonomy_service

logger = get_logger(__name__)


class MatchingService:
    def __init__(self):
        self.settings = get_settings()
        self.index = VectorIndex(embedding_service.dim)
        self.rebuild_index()

    def rebuild_index(self):
        """Embed every job and rebuild the vector index.

        Embeddings are cached on disk per job text, so a restart or a single
        newly posted job only encodes what actually changed - re-encoding the
        whole corpus takes minutes once the CSV holds thousands of jobs.
        """
        jobs = job_service.list()
        if not jobs:
            return
        texts = [f"{j.title}. {j.description} Skills: {', '.join(j.skills)}" for j in jobs]
        job_ids = [j.job_id for j in jobs]

        cache = self._load_cache()
        keys = [self._text_key(t) for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in cache]
        if missing:
            logger.info("Encoding %d of %d jobs (%d served from cache).",
                        len(missing), len(texts), len(texts) - len(missing))
            fresh = embedding_service.encode([texts[i] for i in missing])
            for i, vec in zip(missing, fresh):
                cache[keys[i]] = np.asarray(vec, dtype=np.float32)
            self._save_cache(cache, keys)
        else:
            logger.info("All %d job embeddings served from cache.", len(texts))

        vectors = np.vstack([cache[k] for k in keys]).astype(np.float32)
        self.index.rebuild(job_ids, vectors)

    @staticmethod
    def _text_key(text: str) -> str:
        """Cache key for one job's indexed text. Includes the embedding
        dimension so switching model/PCA never reuses wrong-width vectors."""
        return hashlib.sha256(f"{embedding_service.dim}\x00{text}".encode("utf-8")).hexdigest()

    def _load_cache(self) -> dict:
        """Read the on-disk embedding cache as {text_key: vector}."""
        path = self.settings.job_embeddings_cache_path
        if not os.path.exists(path):
            return {}
        try:
            with np.load(path, allow_pickle=False) as data:
                keys = data["keys"]
                vectors = data["vectors"]
            if len(keys) != len(vectors) or vectors.shape[1] != embedding_service.dim:
                logger.info("Embedding cache has a different vector width; ignoring it.")
                return {}
            return {str(k): vectors[i].astype(np.float32) for i, k in enumerate(keys)}
        except Exception as exc:
            logger.warning("Could not read job embedding cache: %s", exc)
            return {}

    def _save_cache(self, cache: dict, live_keys: list):
        """Persist the cache, dropping vectors for jobs that no longer exist."""
        path = self.settings.job_embeddings_cache_path
        keep = [k for k in dict.fromkeys(live_keys) if k in cache]
        if not keep:
            return
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            np.savez(path, keys=np.array(keep),
                     vectors=np.vstack([cache[k] for k in keep]).astype(np.float32))
            logger.info("Cached %d job embeddings to %s", len(keep), path)
        except Exception as exc:
            logger.warning("Could not write job embedding cache: %s", exc)

    def _jaccard(self, a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        a_low = {x.lower() for x in a}
        b_low = {x.lower() for x in b}
        return len(a_low & b_low) / len(a_low | b_low)

    def match_resume(self, resume_text: str, top_k: int = 10) -> list[MatchResult]:
        query = embedding_service.encode(resume_text)[0]
        candidates = self.index.search(query, top_k=max(top_k * 3, top_k))
        resume_skills = self._extract_skills(resume_text)
        expanded_resume = taxonomy_service.expand(list(resume_skills))
        results = []
        for job_id, semantic in candidates:
            job = job_service.get(job_id)
            if job is None:
                continue
            job_skills = set(job.skills)
            skill_score = self._jaccard(expanded_resume, taxonomy_service.expand(job.skills))
            final = (self.settings.semantic_weight * max(semantic, 0.0)
                     + self.settings.skill_weight * skill_score)
            matched = sorted(s for s in job_skills
                             if s.lower() in {x.lower() for x in expanded_resume})
            missing = sorted(job_skills - set(matched))
            results.append(MatchResult(job=job, semantic_score=round(max(semantic, 0.0), 4),
                                       skill_score=round(skill_score, 4),
                                       final_score=round(final, 4),
                                       matched_skills=matched, missing_skills=missing))
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results[:top_k]

    def semantic_search(self, query_text: str, top_k: int = 10):
        query = embedding_service.encode(query_text)[0]
        hits = self.index.search(query, top_k=top_k)
        out = []
        for job_id, score in hits:
            job = job_service.get(job_id)
            if job:
                out.append({"job": job.model_dump(), "score": round(max(score, 0.0), 4)})
        return out

    def _extract_skills(self, text: str) -> set:
        """Match known taxonomy skills (via aliases) inside free text."""
        return taxonomy_service.match_in_text(text)


matching_service = MatchingService()
