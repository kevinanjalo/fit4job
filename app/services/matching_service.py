"""Hybrid semantic + skill-overlap job matching.

Score_Final = alpha * cosine similarity (SBERT embeddings, FAISS retrieval)
            + beta  * Jaccard similarity over taxonomy-expanded skill sets.
"""
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
        jobs = job_service.list()
        if not jobs:
            return
        texts = [f"{j.title}. {j.description} Skills: {', '.join(j.skills)}" for j in jobs]
        vectors = embedding_service.encode(texts)
        self.index.rebuild([j.job_id for j in jobs], vectors)

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
