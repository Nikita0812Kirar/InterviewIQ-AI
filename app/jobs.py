import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime


REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"


ROLE_SEARCH_TERMS = {
    "Data Analyst": "data analyst sql",
    "Data Scientist": "data scientist machine learning python",
    "Python Developer": "python developer",
    "Frontend Developer": "frontend developer react",
    "Backend Developer": "backend developer api",
    "Full Stack Developer": "full stack developer",
    "SQL Developer": "sql developer database",
    "HR Interview": "human resources",
    "Behavioral Interview": "software developer",
}


def suggested_job_query(interview_role: str | None, skills: list[str]) -> str:
    if interview_role in ROLE_SEARCH_TERMS:
        return ROLE_SEARCH_TERMS[interview_role]
    if skills:
        return " ".join(skills[:3])
    return "software developer"


def fetch_live_jobs(query: str, limit: int = 18) -> dict[str, object]:
    params = {"limit": str(max(1, min(limit, 30)))}
    if query:
        params["search"] = query
    url = f"{REMOTIVE_API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "AI-Interview-Simulator/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "source": "Remotive",
            "source_url": REMOTIVE_API_URL,
            "query": query,
            "jobs": [],
            "error": f"Could not load live jobs right now: {exc}",
        }

    jobs = [_clean_job(job) for job in payload.get("jobs", [])[:limit]]
    return {
        "source": "Remotive",
        "source_url": "https://remotive.com/",
        "query": query,
        "jobs": jobs,
        "error": "",
    }


def _clean_job(job: dict) -> dict[str, str]:
    description = _plain_text(job.get("description", ""))
    return {
        "id": str(job.get("id", "")),
        "title": str(job.get("title", "Untitled role")),
        "company": str(job.get("company_name", "Unknown company")),
        "url": str(job.get("url", "")),
        "category": str(job.get("category", "Remote")),
        "job_type": _titleize(job.get("job_type", "")),
        "location": str(job.get("candidate_required_location", "Remote")),
        "salary": str(job.get("salary") or "Salary not listed"),
        "published": _format_date(job.get("publication_date", "")),
        "summary": description[:260] + ("..." if len(description) > 260 else ""),
    }


def _plain_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", str(html))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _titleize(value: object) -> str:
    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else "Remote"


def _format_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "Recently posted"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except ValueError:
        return text[:10] or "Recently posted"
