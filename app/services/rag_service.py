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


CHUNK_SIZE = 700          # characters per chunk, about a paragraph of prose
CHUNK_OVERLAP = 150       # carried over so a claim split across a boundary
                          # still appears whole in one chunk


def _split_chunk(text: str,
                 size: int = CHUNK_SIZE,
                 overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split an oversized passage into overlapping, sentence-aligned pieces.

    Markdown converted from books produces paragraphs of 8,000-12,000
    characters. Embedding one of those as a single vector blurs every topic it
    covers together, so retrieval returns a blob where only a line or two is
    relevant. Splitting to a uniform size makes the vectors specific, and the
    overlap stops a sentence that straddles a boundary from being lost."""
    text = text.strip()
    if len(text) <= size:
        return [text]

    pieces, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer a sentence boundary, then any whitespace, in the last
            # quarter of the window so pieces do not end mid-word.
            window = text.rfind(". ", start + size * 3 // 4, end)
            if window == -1:
                window = text.rfind(" ", start + size * 3 // 4, end)
            if window != -1:
                end = window + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


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
            # Drop heading-only blocks: they retrieve well on topic words but
            # carry no information for the model to ground an answer on.
            paragraphs = [p for p in paragraphs if not p.lstrip().startswith("#")]
            for p in paragraphs:
                for piece in _split_chunk(p):
                    self.chunks.append({"source": path.stem, "text": piece})
        if self.chunks:
            self.vectors = embedding_service.encode([c["text"] for c in self.chunks])
        logger.info("Knowledge base indexed: %d chunks", len(self.chunks))

    def retrieve(self, query: str, top_k: int = 4,
                 sources: set[str] | None = None) -> list[dict]:
        """Return the top_k most similar chunks, optionally restricted to
        specific source documents.

        The corpus is dominated by a few large books, so a query whose topic
        those books also discuss will fill every slot with them. Restricting
        the candidate set per tool keeps retrieval on topic."""
        if not self.chunks:
            return []
        q = embedding_service.encode(query)[0]
        sims = self.vectors @ q
        order = np.argsort(-sims)
        if sources:
            order = [i for i in order if self.chunks[i]["source"] in sources]
        return [self.chunks[i] for i in order[:top_k]]

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



_key_cursor = 0
_model_cursor = 0


def _call_gemini(prompt: str) -> str | None:
    """Generate with Gemini, falling back across keys and models.

    Keys differ in what they can serve: newer projects reject gemini-2.5-flash,
    older ones reject gemini-3.6-flash, and any key can exhaust its daily quota.
    Each key is tried against each configured model until one combination
    works, and that pair is remembered for the next call. Returns None once
    everything has failed, leaving the offline template generator in charge."""
    global _key_cursor, _model_cursor

    settings = get_settings()
    keys = settings.gemini_api_keys
    models = settings.gemini_models
    if not keys or not models:
        return None

    import google.generativeai as genai

    last_error = None
    for k in range(len(keys)):
        key_index = (_key_cursor + k) % len(keys)
        genai.configure(api_key=keys[key_index])

        for m in range(len(models)):
            model_index = (_model_cursor + m) % len(models)
            try:
                response = genai.GenerativeModel(models[model_index]).generate_content(prompt)
                _key_cursor, _model_cursor = key_index, model_index
                return response.text
            except Exception as exc:
                last_error = exc
                text = str(exc)
                # A model this key cannot serve: try the next model on the same
                # key. Anything else (quota, auth) means move on to the next key.
                if "404" in text or "not available" in text or "not found" in text.lower():
                    continue
                break
        logger.warning("Gemini key %d/%d unusable (%s); trying the next key.",
                       key_index + 1, len(keys), last_error)

    logger.warning("All %d Gemini key(s) failed, using offline generator: %s",
                   len(keys), last_error)
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


CAREER_SOURCES = {"career_development_reference", "career_development"}
CAREER_TOP_K = 6


def _career_query(resume_text: str, limit: int = 8) -> str:
    """Retrieval query for career advice, phrased to match how the career
    reference document states its guidance.

    A generic query such as "career development skill acquisition IT" retrieves
    generic career philosophy and never reaches the paragraphs that actually
    answer the question, which are written as "A professional with experience
    in X, Y and Z is well suited to the A career track". Echoing the candidate's
    own skills in that sentence form retrieves those paragraphs instead."""
    from app.services.resume_parser import parse_resume

    try:
        skills = parse_resume(resume_text).get("detected_skills") or []
    except Exception:
        skills = []
    return ("career track well suited to a professional with experience in "
            + " ".join(skills[:limit])
            + " next three skills to learn six month plan")


def career_recommendation(resume_text: str) -> dict:
    chunks = knowledge_base.retrieve(_career_query(resume_text),
                                     top_k=CAREER_TOP_K, sources=CAREER_SOURCES)
    context = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)
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
