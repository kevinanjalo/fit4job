"""Semantic matching, search, resume upload and AI career endpoints."""
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.models.schemas import (InterviewPrepRequest, MatchRequest, ResumeFeedbackRequest,
                                RoadmapRequest, SearchRequest, SkillGapRequest)
from app.services import (analytics_service, cv_service, rag_service, resume_parser,
                          roadmap_display, skill_gap_service)
from app.services.matching_service import matching_service
import json
from pathlib import Path

CATEGORIES_PATH = Path("data/roadmap_categories.json")


def _resolve_resume_text(resume_text, cv_id) -> str:
    """Prefer an explicitly pasted resume; otherwise pull the stored text of a
    saved CV selected by the user."""
    if resume_text and resume_text.strip():
        return resume_text
    if cv_id:
        cv = cv_service.get_cv(cv_id)
        if cv and cv.get("text"):
            return cv["text"]
        raise HTTPException(status_code=404, detail="Selected CV not found or has no readable text")
    raise HTTPException(status_code=422, detail="Provide resume text or select a saved CV")

router = APIRouter(tags=["matching"])


@router.post("/match")
def match(payload: MatchRequest):
    text = _resolve_resume_text(payload.resume_text, payload.cv_id)
    analytics_service.track("match")
    return [r.model_dump() for r in matching_service.match_resume(text, payload.top_k)]


@router.post("/search")
def search(payload: SearchRequest):
    analytics_service.track("semantic_search")
    return matching_service.semantic_search(payload.query, payload.top_k)


@router.post("/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    text = resume_parser.extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file")
    analytics_service.track("resume_upload")
    return {"text": text, "parsed": resume_parser.parse_resume(text)}


@router.post("/skill-gap")
def skill_gap(payload: SkillGapRequest):
    text = _resolve_resume_text(payload.resume_text, payload.cv_id)
    try:
        analytics_service.track("skill_gap")
        return skill_gap_service.analyze(text, payload.job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/roadmap")
def roadmap(payload: RoadmapRequest):
    try:
        analytics_service.track("roadmap")
        return skill_gap_service.personalized_roadmap(payload.domain, payload.known_skills)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/roadmaps")
def list_roadmaps():
    # Derive the display name from the file stem, not the scraped "domain"
    # field, so acronyms render correctly ("AI Data Scientist", "MLOps").
    return {k: roadmap_display.display_name(k) for k in skill_gap_service.load_roadmaps()}


@router.post("/interview-prep")
def interview_prep(payload: InterviewPrepRequest):
    text = None
    if payload.resume_text or payload.cv_id:
        try:
            text = _resolve_resume_text(payload.resume_text, payload.cv_id)
        except HTTPException:
            text = None
    try:
        analytics_service.track("interview_prep")
        return rag_service.generate_interview_questions(payload.job_id, text,
                                                        payload.question_count)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/resume-feedback")
def resume_feedback(payload: ResumeFeedbackRequest):
    analytics_service.track("resume_feedback")
    return rag_service.generate_resume_feedback(payload.resume_text, payload.job_id)


@router.post("/career-advice")
def career_advice(payload: ResumeFeedbackRequest):
    analytics_service.track("career_advice")
    return rag_service.career_recommendation(payload.resume_text)


@router.get("/roadmap-graph/{name}")
def roadmap_graph(name: str):
    """Node graph for the interactive roadmap tree view, with scrape-artifact
    nodes dropped and labels tidied so the tree reads cleanly."""
    safe = "".join(c for c in name if c.isalnum() or c == "_")
    path = Path("data/roadmap_graphs") / f"{safe}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Roadmap graph not found")
    graph = json.loads(path.read_text(encoding="utf-8"))
    graph["topic"] = roadmap_display.display_name(safe)
    clean_nodes = []
    for node in graph.get("nodes", []):
        label = roadmap_display.clean_label(node.get("label", ""))
        if node.get("type") == "root":
            node["label"] = graph["topic"]
            clean_nodes.append(node)
        elif not roadmap_display.is_junk(label):
            node["label"] = label
            clean_nodes.append(node)
    graph["nodes"] = clean_nodes
    return graph


@router.get("/roadmap-graphs")
def roadmap_graphs():
    out = {}
    for p in sorted(Path("data/roadmap_graphs").glob("*.json")):
        out[p.stem] = roadmap_display.display_name(p.stem)
    return out


@router.get("/roadmap-categories")
def roadmap_categories():
    """Roadmaps grouped by field (AI & Data, Mobile, Web, ...) for the
    sectioned roadmap explorer. Only stems that have a graph file are returned."""
    available = {p.stem for p in Path("data/roadmap_graphs").glob("*.json")}
    groups = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8")) if CATEGORIES_PATH.exists() else {}
    out = []
    assigned = set()
    for title, stems in groups.items():
        items = [{"key": s, "name": roadmap_display.display_name(s)} for s in stems if s in available]
        assigned.update(s for s in stems if s in available)
        if items:
            out.append({"category": title, "roadmaps": items})
    leftover = [{"key": s, "name": roadmap_display.display_name(s)} for s in sorted(available - assigned)]
    if leftover:
        out.append({"category": "More", "roadmaps": leftover})
    return out


from pydantic import BaseModel


class NodeInfoRequest(BaseModel):
    roadmap: str
    node: str


@router.post("/roadmap-node-info")
def roadmap_node_info(payload: NodeInfoRequest):
    analytics_service.track("roadmap_node_info")
    return rag_service.explain_roadmap_node(payload.roadmap, payload.node)
