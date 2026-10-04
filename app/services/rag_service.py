"""Retrieval-Augmented Generation module.

Pipeline (kept identical to the research design):
  1. Retrieve: encode the query with the same SBERT embeddings and fetch the
     most relevant knowledge-base chunks from the ChromaDB vector store, plus
     the target job description.
  2. Prompt: instruct the LLM (Gemini) with the retrieved context.
  3. Generate: return grounded interview questions, resume feedback or
     career advice.

If GEMINI_API_KEY is missing or the API is unreachable, a deterministic
template-based generator produces useful output so the platform still works
offline. Your existing trained RAG pipeline can replace this module by
implementing the same three public functions.
"""
import hashlib
import re
import threading
from pathlib import Path
from app.config import get_settings
from app.core.logging import get_logger
from app.services.embedding_service import embedding_service
from app.services.job_service import job_service

logger = get_logger(__name__)


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


SOURCE_HASH_KEY = "doc_hash"
# Part of the store's fingerprint: changing the chunking rules makes the
# stored chunks stale, so they are rebuilt to match.
CHUNKER_VERSION = f"v1-{CHUNK_SIZE}-{CHUNK_OVERLAP}"


def _safe_name(name: str) -> str:
    """Restrict a document name to a plain file stem inside the KB folder."""
    return "".join(c for c in name if c.isalnum() or c in "-_").strip("-_")


def _chunk_document(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 60]
    # Drop heading-only blocks: they retrieve well on topic words but
    # carry no information for the model to ground an answer on.
    paragraphs = [p for p in paragraphs if not p.lstrip().startswith("#")]
    return [piece for p in paragraphs for piece in _split_chunk(p)]


class KnowledgeBase:
    """RAG knowledge base persisted in a ChromaDB vector store.

    The Markdown files in the knowledge base folder are the source of truth.
    Each is chunked, embedded with the platform's SBERT encoder and stored in
    Chroma together with a hash of the file, so on startup only new or edited
    documents are re-embedded and deleted ones are removed. If the encoder or
    the chunking changes, stored vectors are no longer comparable with new
    queries and the whole collection is rebuilt."""

    def __init__(self):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        settings = get_settings()
        self.kb_dir = Path(settings.knowledge_base_dir)
        self.chunks: list[dict] = []
        self._lock = threading.RLock()
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False))
        self._collection_name = settings.chroma_collection
        self._fingerprint = f"{embedding_service.fingerprint}|{CHUNKER_VERSION}"
        self._collection = self._open_collection()
        self.sync()

    def _open_collection(self, reset: bool = False):
        if not reset:
            try:
                col = self._client.get_collection(self._collection_name)
            except Exception:
                col = None  # first run: no collection yet
            if col is not None:
                if (col.metadata or {}).get("fingerprint") == self._fingerprint:
                    return col
                logger.info("Knowledge base vectors were built with a different encoder "
                            "or chunking; rebuilding the vector store.")
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass
        # Embeddings are unit length, so cosine distance ranks chunks exactly
        # as the dot product of the original in-memory index did.
        return self._client.create_collection(
            self._collection_name,
            metadata={"fingerprint": self._fingerprint},
            configuration={"hnsw": {"space": "cosine"}})

    def _source_files(self) -> dict[str, Path]:
        return {p.stem: p for p in sorted(self.kb_dir.glob("*.md")) if p.name != "README.md"}

    def _stored_hashes(self) -> dict[str, str]:
        metas = self._collection.get(include=["metadatas"])["metadatas"] or []
        return {m["source"]: m[SOURCE_HASH_KEY] for m in metas}

    def _index_document(self, source: str, text: str) -> int:
        """Replace every stored chunk of one document with freshly embedded ones."""
        self._collection.delete(where={"source": source})
        pieces = _chunk_document(text)
        if not pieces:
            return 0
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        vectors = embedding_service.encode(pieces)
        batch = self._client.get_max_batch_size()
        for start in range(0, len(pieces), batch):
            idx = range(start, min(start + batch, len(pieces)))
            self._collection.add(
                ids=[f"{source}::{i}" for i in idx],
                documents=[pieces[i] for i in idx],
                embeddings=vectors[idx.start:idx.stop].tolist(),
                metadatas=[{"source": source, "chunk": i, SOURCE_HASH_KEY: digest} for i in idx])
        return len(pieces)

    def _load_chunks(self):
        got = self._collection.get(include=["documents", "metadatas"])
        rows = sorted(zip(got["metadatas"] or [], got["documents"] or []),
                      key=lambda r: (r[0]["source"], r[0]["chunk"]))
        self.chunks = [{"source": m["source"], "text": d} for m, d in rows]

    def sync(self) -> dict:
        """Bring the vector store in line with the files on disk, embedding
        only documents that are new or have changed since they were stored."""
        added, updated, removed = [], [], []
        with self._lock:
            files = self._source_files()
            stored = self._stored_hashes()
            for source in stored.keys() - files.keys():
                self._collection.delete(where={"source": source})
                removed.append(source)
            for source, path in files.items():
                text = path.read_text(encoding="utf-8")
                if stored.get(source) == hashlib.sha256(text.encode("utf-8")).hexdigest():
                    continue
                if self._index_document(source, text):
                    (updated if source in stored else added).append(source)
            self._load_chunks()
        logger.info("Knowledge base vector store: %d chunks from %d documents "
                    "(added: %s; updated: %s; removed: %s)",
                    len(self.chunks), len(self.documents()),
                    ", ".join(added) or "none", ", ".join(updated) or "none",
                    ", ".join(removed) or "none")
        return {"added": added, "updated": updated, "removed": removed,
                "chunks": len(self.chunks)}

    def rebuild(self) -> dict:
        """Drop the vector store and re-embed every document from scratch."""
        with self._lock:
            self._collection = self._open_collection(reset=True)
            return self.sync()

    def save_document(self, name: str, content: str) -> str:
        """Create or overwrite a Markdown document and re-index only it."""
        source = _safe_name(name)
        if not source or source.lower() == "readme":
            raise ValueError("Invalid document name")
        with self._lock:
            self.kb_dir.mkdir(parents=True, exist_ok=True)
            (self.kb_dir / f"{source}.md").write_text(content, encoding="utf-8")
            self._index_document(source, content)
            self._load_chunks()
        return source

    def read_document(self, name: str) -> str | None:
        path = self._source_files().get(_safe_name(name))
        return path.read_text(encoding="utf-8") if path else None

    def delete_document(self, name: str) -> bool:
        source = _safe_name(name)
        with self._lock:
            path = self._source_files().get(source)
            if path is None:
                return False
            path.unlink()
            self._collection.delete(where={"source": source})
            self._load_chunks()
        return True

    def retrieve(self, query: str, top_k: int = 4,
                 sources: set[str] | None = None) -> list[dict]:
        """Return the top_k most similar chunks, optionally restricted to
        specific source documents.

        The corpus is dominated by a few large books, so a query whose topic
        those books also discuss will fill every slot with them. Restricting
        the candidate set per tool keeps retrieval on topic."""
        if not self.chunks:
            return []
        q = embedding_service.encode(query)[0].tolist()
        where = {"source": {"$in": sorted(sources)}} if sources else None
        res = self._collection.query(query_embeddings=[q], n_results=top_k, where=where,
                                     include=["documents", "metadatas", "distances"])
        return [{"source": m["source"], "text": d, "score": round(1.0 - dist, 4)}
                for m, d, dist in zip(res["metadatas"][0], res["documents"][0],
                                      res["distances"][0])]

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



_model_cursor = 0
_configured_key: str | None = None


def _call_gemini(prompt: str) -> str | None:
    """Generate with Gemini, always starting from the original first key.

    GEMINI_API_KEY is the project's own key, so every call begins there; the
    extra keys exist only to keep the platform answering after it hits its
    daily quota, and we fall back to them rather than settling on them. Keys
    also differ in what they can serve (a model one project rejects with a 404
    another serves fine), so each key is tried against each configured model
    until one combination works. The working model is remembered so later calls
    do not re-probe a model this key cannot serve. Returns None once everything
    has failed, leaving the offline template generator in charge."""
    global _model_cursor, _configured_key

    settings = get_settings()
    keys = settings.gemini_api_keys
    models = settings.gemini_models
    if not keys or not models:
        return None

    import google.generativeai as genai

    last_error = None
    for key_index, key in enumerate(keys):
        # configure() rebuilds the transport, which costs seconds on the next
        # call, so skip it while we are still on the key already configured.
        if key != _configured_key:
            genai.configure(api_key=key)
            _configured_key = key

        for m in range(len(models)):
            model_index = (_model_cursor + m) % len(models)
            try:
                response = genai.GenerativeModel(models[model_index]).generate_content(prompt)
                _model_cursor = model_index
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
