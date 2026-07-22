"""Lightweight analytics and system monitoring."""
import platform
import time
from collections import Counter
from app.core import firebase
from app.services.job_service import job_service

_start_time = time.time()
_request_counter: Counter = Counter()


def track(event: str):
    _request_counter[event] += 1


def summary() -> dict:
    jobs = job_service.list()
    users = firebase.collection("users").all()
    by_level = Counter(j.experience_level for j in jobs)
    by_location = Counter(j.location for j in jobs)
    return {
        "total_jobs": len(jobs),
        "total_users": len(users),
        "jobs_by_level": dict(by_level),
        "jobs_by_location": dict(by_location),
        "events": dict(_request_counter),
    }


def system_status() -> dict:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu, mem = None, None
    return {
        "uptime_seconds": int(time.time() - _start_time),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_percent": cpu,
        "memory_percent": mem,
    }
