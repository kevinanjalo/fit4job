"""Job repository: loads dummy jobs from CSV, supports CRUD via admin."""
import csv
import re
import time
import uuid
from pathlib import Path
from typing import List, Optional
from app.models.schemas import Job, JobCreate

JOBS_CSV = Path("data/jobs.csv")

# Field areas for the "filter by area" control. A job belongs to an area when any
# keyword appears in its title or skills. Keys must match the options in the
# jobs page filter (templates/jobs.html).
AREA_KEYWORDS = {
    "AI & Data": ["ai", "artificial intelligence", "machine learning", "deep learning",
                  "data scien", "data analy", "nlp", "pytorch", "tensorflow", "mlops",
                  "data engineer", "computer vision", "llm", "ml engineer", "big data"],
    "Web Development": ["react", "angular", "vue", "javascript", "typescript", "html", "css",
                        "node", "nodejs", "next.js", "frontend", "front end", "front-end", "backend",
                        "back end", "back-end", "php", "laravel", "django", ".net", "asp.net",
                        "dotnet", "wordpress", "web develop", "full stack", "full-stack"],
    "Mobile": ["android", "ios", "flutter", "react native", "kotlin", "swift", "swiftui",
               "mobile app", "mobile develop", "xamarin"],
    "DevOps & Cloud": ["devops", "docker", "kubernetes", "aws", "azure", "gcp", "terraform",
                       "ci/cd", "cloud", "jenkins", "ansible", "sre", "site reliability"],
    "Data & Databases": ["sql", "postgres", "postgresql", "mysql", "mongodb", "redis",
                         "elasticsearch", "database", "oracle", "snowflake", "data warehouse"],
    "Security & QA": ["security", "cyber", "penetration", "pentest", "qa", "quality assurance",
                      "test automation", "selenium", "tester", "sdet"],
    "Design": ["ux", "ui/ux", "figma", "product design", "graphic design", "interaction design",
               "web design", "visual design", "user experience", "user interface"],
}


class JobService:
    def __init__(self):
        self._jobs: dict = {}
        self.load_csv()

    def load_csv(self):
        self._jobs = {}
        if not JOBS_CSV.exists():
            return
        with open(JOBS_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["skills"] = [s.strip() for s in row.get("skills", "").split(";") if s.strip()]
                row.setdefault("owner", "")
                if row.get("owner") is None:
                    row["owner"] = ""
                self._jobs[row["job_id"]] = Job(**row)

    def save_csv(self):
        with open(JOBS_CSV, "w", newline="", encoding="utf-8") as f:
            fields = ["job_id", "title", "company", "location", "job_type", "experience_level",
                      "salary_range", "description", "skills", "industry", "posted_date", "owner"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for job in self._jobs.values():
                d = job.model_dump()
                d["skills"] = ";".join(d["skills"])
                w.writerow(d)

    def list(self, query: str = "", location: str = "", level: str = "", area: str = "") -> List[Job]:
        jobs = list(self._jobs.values())
        if query:
            q = query.lower()
            jobs = [j for j in jobs if q in j.title.lower() or q in j.company.lower()
                    or any(q in s.lower() for s in j.skills)]
        if location:
            jobs = [j for j in jobs if location.lower() in j.location.lower()]
        if level:
            jobs = [j for j in jobs if j.experience_level.lower() == level.lower()]
        if area and area in AREA_KEYWORDS:
            kws = AREA_KEYWORDS[area]
            jobs = [j for j in jobs if self._matches_area(j, kws)]
        return jobs

    @staticmethod
    def _matches_area(job: Job, keywords: list) -> bool:
        # Word-boundary match so short keywords ("ai", "ux", "qa") match real
        # tokens only - never inside "training", "linux", "square", etc.
        haystack = (job.title + " " + " ".join(job.skills)).lower()
        for kw in keywords:
            if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", haystack):
                return True
        return False

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def create(self, payload: JobCreate, owner: str = "") -> Job:
        job = Job(job_id=f"J{uuid.uuid4().hex[:6].upper()}",
                  posted_date=time.strftime("%Y-%m-%d"), owner=owner, **payload.model_dump())
        self._jobs[job.job_id] = job
        self.save_csv()
        return job

    def update(self, job_id: str, payload: JobCreate) -> Optional[Job]:
        if job_id not in self._jobs:
            return None
        existing = self._jobs[job_id]
        job = Job(job_id=job_id, posted_date=existing.posted_date,
                  owner=existing.owner, **payload.model_dump())
        self._jobs[job_id] = job
        self.save_csv()
        return job

    def list_by_owner(self, owner: str) -> List[Job]:
        return [j for j in self._jobs.values() if j.owner == owner]

    def is_owner(self, job_id: str, owner: str) -> bool:
        job = self._jobs.get(job_id)
        return job is not None and job.owner == owner

    def delete(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self.save_csv()
            return True
        return False


job_service = JobService()
