"""Public job listing and detail endpoints."""
from fastapi import APIRouter, HTTPException
from app.services.job_service import job_service
from app.services import analytics_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(q: str = "", location: str = "", level: str = "", area: str = "",
             page: int = 0, page_size: int = 0):
    """List jobs, filtered server-side by keyword/location/level/area.

    Backwards compatible: with no ``page_size`` a plain array is returned (used
    by the admin dashboard and tests). When ``page_size`` > 0 a paginated
    envelope ``{items, total, page, page_size, total_pages}`` is returned so the
    public jobs page can show one page of results at a time.
    """
    analytics_service.track("jobs_list")
    jobs = job_service.list(q, location, level, area)
    if page_size and page_size > 0:
        total = len(jobs)
        current = max(page, 1)
        start = (current - 1) * page_size
        window = jobs[start:start + page_size]
        return {
            "items": [j.model_dump() for j in window],
            "total": total,
            "page": current,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    return [j.model_dump() for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: str):
    job = job_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    analytics_service.track("job_detail")
    return job.model_dump()
