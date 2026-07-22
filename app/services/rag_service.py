"""Retrieval-Augmented Generation module.

Pipeline (kept identical to the research design):
  1. Retrieve: encode the query with the same SBERT embeddings and fetch the
     most relevant knowledge-base chunks plus the target job description.
  2. Prompt: instruct the LLM (Gemini) with the retrieved context.
  3. Generate: return grounded interview questions, resume feedback or
     career advice.

If GEMINI_API_KEY is missing or the API is unreachable, a deterministic
template-based generator produces useful output so the platform still works
offline. Your existing trained RAG pipeline can replace this module by
implementing the same three public functions.
"""
import re
from pathlib import Path
import numpy as np
from app.config import get_settings
from app.core.logging import get_logger
from app.services.embedding_service import embedding_service
from app.services.job_service import job_service

logger = get_logger(__name__)
KB_DIR = Path("data/knowledge_base")


class KnowledgeBase:
    def __init__(self):
        self.chunks: list[dict] = []
        self.vectors = None
        self.rebuild()

    def rebuild(self):
        self.chunks = []
        for path in sorted(KB_DIR.glob("*.md")):
            if path.name == "README.md":
                continue
            text = path.read_text(encoding="utf-8")
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 60]
            for p in paragraphs:
                self.chunks.append({"source": path.stem, "text": p})
        if self.chunks:
            self.vectors = embedding_service.encode([c["text"] for c in self.chunks])
        logger.info("Knowledge base indexed: %d chunks", len(self.chunks))

    def retrieve(self, query: str, top_k: int = 4) -> list[dict]:
        if not self.chunks:
            return []
        q = embedding_service.encode(query)[0]
        sims = self.vectors @ q
        order = np.argsort(-sims)[:top_k]
        return [self.chunks[i] for i in order]

    def documents(self) -> list[str]:
        return sorted({c["source"] for c in self.chunks})


knowledge_base = KnowledgeBase()

def clean_output(text: str) -> str:
    """Normalise LLM output into clean plain text: strip markdown markers
    (**bold**, *italic*, # headings, backticks) while keeping numbering,
    line breaks and list structure readable."""
    out = text
    out = re.sub(r"```[a-zA-Z]*\n?", "", out)
    out = out.replace("`", "")
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    out = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", out)
    out = re.sub(r"^#{1,6}\s*", "", out, flags=re.M)
    out = re.sub(r"^\s*[-\u2022]\s+", "- ", out, flags=re.M)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()



def _call_gemini(prompt: str) -> str | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        logger.warning("Gemini call failed, using offline generator: %s", exc)
        return None


def _context_block(query: str) -> str:
    chunks = knowledge_base.retrieve(query)
    return "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


def generate_interview_questions(job_id: str, resume_text: str | None, count: int = 6) -> dict:
    job = job_service.get(job_id)
    if job is None:
        raise ValueError("Job not found")
    context = _context_block(f"interview preparation {job.title} {' '.join(job.skills)}")
    prompt = (
        "You are an expert technical interviewer. Respond in plain text only, no markdown symbols such as asterisks or hashes. Structure the answer with short section titles ending in a colon, followed by short numbered points or dashes. Keep every sentence short and simple. Never write long paragraphs.  Using only the job description and "
        "reference context below, generate "
        f"{count} targeted interview questions for this role: a mix of technical, "
        "scenario-based and behavioural questions. Number each question and add a "
        "one-line hint on what a strong answer covers.\n\n"
        f"JOB DESCRIPTION:\nTitle: {job.title}\nSkills: {', '.join(job.skills)}\n{job.description}\n\n"
        f"CANDIDATE RESUME (optional):\n{(resume_text or 'Not provided')[:3000]}\n\n"
        f"REFERENCE CONTEXT:\n{context}"
    )
    text = _call_gemini(prompt)
    mode = "gemini" if text is not None else "offline"
    if text is None:
        questions = []
        for i, skill in enumerate((job.skills * 3)[:count], 1):
            questions.append(f"{i}. Describe a project where you used {skill} in production for a "
                             f"{job.title} responsibility. Hint: cover the problem, your design "
                             f"decisions, trade-offs and the measurable outcome.")
        text = "\n".join(questions)
    return {"job_id": job_id, "job_title": job.title, "questions": clean_output(text), "mode": mode}


def generate_resume_feedback(resume_text: str, job_id: str | None) -> dict:
    job = job_service.get(job_id) if job_id else None
    target = f"Target role: {job.title}. Required skills: {', '.join(job.skills)}.\n{job.description}" if job else "No specific target role."
    context = _context_block("resume writing improvement technology roles")
    prompt = (
        "You are a professional technical resume reviewer. Respond in plain text only, no markdown symbols such as asterisks or hashes. Structure the answer with short section titles ending in a colon, followed by short numbered points or dashes. Keep every sentence short and simple. Never write long paragraphs.  Using the reference context, "
        "give structured feedback on the resume below: strengths, weaknesses, missing "
        "keywords for the target role, and five concrete rewrite suggestions.\n\n"
        f"{target}\n\nRESUME:\n{resume_text[:6000]}\n\nREFERENCE CONTEXT:\n{context}"
    )
    text = _call_gemini(prompt)
    if text is None:
        wc = len(resume_text.split())
        text = (
            "Strengths: resume submitted with detectable structure.\n"
            f"Length check: {wc} words ({'appropriate' if 250 <= wc <= 700 else 'consider adjusting toward 300-600 words'}).\n"
            "Suggestions:\n"
            "1. Start each bullet with a strong action verb and a measurable outcome.\n"
            "2. Mirror genuine skills from the target job description near the top.\n"
            "3. Quantify impact (latency, users, cost, coverage) wherever honest numbers exist.\n"
            "4. Add links to code or live projects.\n"
            "5. Remove generic objectives and unsupported soft-skill claims."
        )
    return {"feedback": clean_output(text)}


def career_recommendation(resume_text: str) -> dict:
    context = _context_block("career development skill acquisition IT")
    prompt = (
        "You are a career advisor for IT professionals in Sri Lanka. Respond in plain text only, no markdown symbols such as asterisks or hashes. Structure the answer with short section titles ending in a colon, followed by short numbered points or dashes. Keep every sentence short and simple. Never write long paragraphs.  Based on the resume "
        "and reference context, recommend the two best-fit career tracks, the next three "
        "skills to learn, and a 6-month plan.\n\n"
        f"RESUME:\n{resume_text[:6000]}\n\nREFERENCE CONTEXT:\n{context}"
    )
    text = _call_gemini(prompt)
    if text is None:
        text = ("Recommended approach: compare your detected skills against the roadmaps in "
                "the Learning section, pick the domain with the highest existing coverage, "
                "and close the earliest incomplete stage first. Re-run job matching monthly "
                "to track how your match scores improve.")
    return {"recommendation": clean_output(text)}


def explain_roadmap_node(roadmap: str, node: str) -> dict:
    """Short, structured explanation of a roadmap topic for the side panel."""
    context = _context_block(f"{node} {roadmap} learning")
    prompt = (
        "You are a friendly IT learning mentor. Respond in plain text only, no markdown "
        "symbols. Explain the topic below for a learner following the given roadmap. "
        "Use exactly this structure, with each section on its own lines:\n"
        "What it is: one short sentence.\n"
        "Why it matters: one short sentence.\n"
        "Start with: two or three short dash points.\n\n"
        f"ROADMAP: {roadmap}\nTOPIC: {node}\n\nREFERENCE CONTEXT:\n{context}"
    )
    text = _call_gemini(prompt)
    if text is None:
        text = (f"What it is: {node} is a topic on the {roadmap} learning path.\n"
                f"Why it matters: it builds the foundation for the stages that follow it.\n"
                "Start with:\n- Read the official documentation or a beginner guide.\n"
                "- Build one small practice project using it.\n"
                "- Revisit it after finishing the next stage to connect ideas.")
    return {"roadmap": roadmap, "node": node, "explanation": clean_output(text)}
