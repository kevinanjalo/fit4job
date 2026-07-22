"""Skill gap analysis against a specific job, mapped to learning roadmaps."""
import json
from pathlib import Path
from app.services import roadmap_display
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.taxonomy_service import taxonomy_service

ROADMAP_DIR = Path("data/roadmaps")


def load_roadmaps() -> dict:
    out = {}
    for path in ROADMAP_DIR.glob("*.json"):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out


def save_roadmap(name: str, data: dict):
    (ROADMAP_DIR / f"{name}.json").write_text(json.dumps(data, indent=2))


def _best_roadmap(job_skills: list, roadmaps: dict) -> str | None:
    """Return the stem of the roadmap whose stages collectively cover the most
    of this job's required skills - i.e. the roadmap most relevant to the job."""
    job_lower = {s.lower() for s in job_skills}
    best_key, best_score = None, 0
    for key, roadmap in roadmaps.items():
        covered = set()
        for stage in roadmap.get("stages", []):
            for skill in stage.get("skills", []):
                if skill.lower() in job_lower:
                    covered.add(skill.lower())
        if len(covered) > best_score:
            best_key, best_score = key, len(covered)
    return best_key


def _find_stage(skill: str, roadmaps: dict, preferred: str | None):
    """Locate a clean roadmap stage that teaches ``skill``.

    Prefers the roadmap most relevant to the job; otherwise takes the first
    clean match in deterministic (alphabetical) order. Returns (stem, stage) or
    (None, None). Stages whose names are scrape artifacts are skipped so the
    guidance never surfaces garbled text.
    """
    target = skill.lower()
    order = ([preferred] if preferred else []) + sorted(k for k in roadmaps if k != preferred)
    for key in order:
        roadmap = roadmaps.get(key)
        if not roadmap:
            continue
        for stage in roadmap.get("stages", []):
            name = roadmap_display.clean_label(stage.get("name", ""))
            if roadmap_display.is_junk(name):
                continue
            if target in {x.lower() for x in stage.get("skills", [])}:
                return key, {**stage, "name": name}
    return None, None


def analyze(resume_text: str, job_id: str) -> dict:
    job = job_service.get(job_id)
    if job is None:
        raise ValueError("Job not found")

    resume_skills = taxonomy_service.expand(list(matching_service._extract_skills(resume_text)))
    have = {s.lower() for s in resume_skills}

    # Display each required skill under its canonical name/casing
    # (so "Pytorch"/"Mlops" from the CSV render as "PyTorch"/"MLOps").
    matched, missing = [], []
    for skill in job.skills:
        canonical = taxonomy_service.canonical(skill)
        (matched if skill.lower() in have else missing).append(canonical)

    roadmaps = load_roadmaps()
    preferred = _best_roadmap(job.skills, roadmaps)
    recommendations, seen = [], set()
    for skill in missing:
        if skill.lower() in seen:
            continue
        seen.add(skill.lower())
        key, stage = _find_stage(skill, roadmaps, preferred)
        if stage is None:
            continue
        recommendations.append({
            "skill": skill,
            "roadmap_key": key,
            "roadmap": roadmap_display.display_name(key),
            "stage": stage["name"],
        })

    coverage = round(len(matched) / len(job.skills), 3) if job.skills else 0.0
    focus = roadmap_display.display_name(preferred) if preferred else None
    focus_key = preferred
    return {"job": job.model_dump(), "matched_skills": matched,
            "missing_skills": missing, "coverage": coverage,
            "focus_roadmap": focus, "focus_roadmap_key": focus_key,
            "learning_recommendations": recommendations}


def personalized_roadmap(domain: str, known_skills: list) -> dict:
    roadmaps = load_roadmaps()
    key = domain.lower().replace(" ", "_")
    roadmap = roadmaps.get(key)
    if roadmap is None:
        for k, v in roadmaps.items():
            if domain.lower() in v["domain"].lower() or domain.lower() in k:
                roadmap, key = v, k
                break
    if roadmap is None:
        available = ", ".join(roadmap_display.display_name(k) for k in sorted(roadmaps))
        raise ValueError(f"Unknown domain. Available: {available}")
    known = {s.lower() for s in taxonomy_service.expand(known_skills)}
    stages = []
    for stage in roadmap["stages"]:
        name = roadmap_display.clean_label(stage.get("name", ""))
        if roadmap_display.is_junk(name):
            continue
        skills = [s for s in stage["skills"] if not roadmap_display.is_junk(roadmap_display.clean_label(s))]
        skills = [roadmap_display.clean_label(s) for s in skills]
        remaining = [s for s in skills if s.lower() not in known]
        resources = [r for r in stage.get("resources", []) if not r.lower().startswith("roadmap.sh")]
        stages.append({"name": name, "skills": skills, "resources": resources,
                       "completed": not remaining, "remaining_skills": remaining})
    return {"domain": roadmap_display.display_name(key), "domain_key": key, "stages": stages}
