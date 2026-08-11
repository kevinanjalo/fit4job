"""Pydantic schemas shared across the API layer."""
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)


class OrgRegister(BaseModel):
    organization_name: str
    email: EmailStr
    password: str = Field(min_length=6)
    website: str = ""
    location: str = ""
    about: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    job_type: str = "Full-time"
    experience_level: str = "Mid"
    salary_range: str = ""
    description: str
    skills: List[str] = []
    industry: str = "Information Technology"
    posted_date: str = ""
    owner: str = ""  # email of the organization that posted this job (blank = seed data)


class JobCreate(BaseModel):
    title: str
    company: str
    location: str
    job_type: str = "Full-time"
    experience_level: str = "Mid"
    salary_range: str = ""
    description: str
    skills: List[str] = []
    industry: str = "Information Technology"


class MatchRequest(BaseModel):
    resume_text: Optional[str] = None
    cv_id: Optional[str] = None
    top_k: int = 10


class MatchResult(BaseModel):
    job: Job
    semantic_score: float
    skill_score: float
    final_score: float
    matched_skills: List[str]
    missing_skills: List[str]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


class InterviewPrepRequest(BaseModel):
    job_id: str
    resume_text: Optional[str] = None
    cv_id: Optional[str] = None
    question_count: int = 6


class ResumeFeedbackRequest(BaseModel):
    resume_text: str
    job_id: Optional[str] = None


class SkillGapRequest(BaseModel):
    resume_text: Optional[str] = None
    cv_id: Optional[str] = None
    job_id: str


class RoadmapRequest(BaseModel):
    domain: str
    known_skills: List[str] = []


class TaxonomyNode(BaseModel):
    name: str
    parents: List[str] = []
    children: List[str] = []
    implies: List[str] = []
