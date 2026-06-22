"""
scrapers.py — F003 Job Scraper Agent
Three scraper functions, each returning (list[dict], list[str]) — jobs + error messages.
  {title, company, location, job_type, remote, description, url, source, date_posted, date_scraped}
"""

import time
import warnings
from datetime import datetime, date

import requests

# Suppress pandas/jobspy deprecation noise
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

DATE_SCRAPED = datetime.now().strftime("%Y-%m-%d")

# Map UI source names → JobSpy site_name values
_JOBSPY_NAME_MAP = {
    "linkedin":     "linkedin",
    "indeed":       "indeed",
    "glassdoor":    "glassdoor",
    "google":       "google",
    "ziprecruiter": "zip_recruiter",
}

JOBSPY_RESULTS_PER_SOURCE = 15
HIMALAYAS_LIMIT           = 20
DELAY_BETWEEN_SOURCES_SEC = 2


def _clean(val) -> str:
    """Convert NaN / None / non-string to empty string."""
    if val is None:
        return ""
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return ""
    except Exception:
        pass
    if isinstance(val, (datetime, date)):
        return str(val)
    return str(val).strip()


def run_jobspy(query: str, location: str, job_type: str, remote: bool,
               sources: list, results_per_source: int = JOBSPY_RESULTS_PER_SOURCE) -> tuple:
    """
    Scrape LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter via JobSpy.
    Returns (jobs: list[dict], errors: list[str]).
    """
    from jobspy import scrape_jobs

    site_names = [_JOBSPY_NAME_MAP[s] for s in sources if s in _JOBSPY_NAME_MAP]
    if not site_names:
        return [], []

    try:
        df = scrape_jobs(
            site_name=site_names,
            search_term=query,
            location=location,
            results_wanted=results_per_source,
            job_type=job_type if job_type != "fulltime" else "fulltime",
            is_remote=remote,
            verbose=0,
        )
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            msg = "Job boards (LinkedIn/Indeed/etc): rate-limited (429) — try again later"
            print(f"[scrapers] JobSpy 429 rate-limited — skipping job boards")
        else:
            msg = f"Job boards: HTTP {status} error — search failed"
            print(f"[scrapers] JobSpy HTTP {status} error: {e}")
        return [], [msg]
    except Exception as e:
        print(f"[scrapers] JobSpy error: {e}")
        return [], [f"Job boards: unexpected error — {e}"]
    finally:
        time.sleep(DELAY_BETWEEN_SOURCES_SEC)

    if df is None or df.empty:
        names = ", ".join(s for s in sources if s in _JOBSPY_NAME_MAP)
        return [], [f"{names}: returned no results (possibly blocked or no matches)"]

    jobs = []
    for _, row in df.iterrows():
        jobs.append({
            "title":        _clean(row.get("title")),
            "company":      _clean(row.get("company")),
            "location":     _clean(row.get("location")),
            "job_type":     _clean(row.get("job_type")),
            "remote":       bool(row.get("is_remote")),
            "description":  _clean(row.get("description")),
            "url":          _clean(row.get("job_url")),
            "source":       _clean(row.get("site")),
            "date_posted":  _clean(row.get("date_posted")),
            "date_scraped": DATE_SCRAPED,
        })

    final_jobs = [j for j in jobs if j["url"]]

    # Detect per-source failures: requested but absent from results
    found_sources = {j["source"] for j in final_jobs}
    errors = []
    _label = {"linkedin": "LinkedIn", "indeed": "Indeed", "glassdoor": "Glassdoor",
               "google": "Google Jobs", "zip_recruiter": "ZipRecruiter"}
    for jobspy_name in site_names:
        if jobspy_name not in found_sources:
            label = _label.get(jobspy_name, jobspy_name)
            errors.append(f"{label}: no results returned (blocked or rate-limited)")

    return final_jobs, errors


def run_himalayas(query: str) -> tuple:
    """
    Search Himalayas remote jobs API.
    Returns (jobs: list[dict], errors: list[str]).
    """
    url = "https://himalayas.app/jobs/api/search"
    for attempt in range(2):
        try:
            resp = requests.get(url, params={"q": query}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429 and attempt == 0:
                print("[scrapers] Himalayas 429 — waiting 60s before retry")
                time.sleep(60)
                continue
            print(f"[scrapers] Himalayas HTTP {status} error: {e}")
            return [], [f"Himalayas: HTTP {status} error — search failed"]
        except Exception as e:
            print(f"[scrapers] Himalayas error: {e}")
            return [], [f"Himalayas: unexpected error — {e}"]
    else:
        return [], ["Himalayas: rate-limited after retry — skipped"]
    time.sleep(1)

    raw_jobs = data.get("jobs", [])
    jobs = []
    for j in raw_jobs:
        company = j.get("companyName") or (j.get("company") or {}).get("name", "")
        locations = j.get("locationRestrictions") or j.get("locations") or []
        location_str = ", ".join(locations) if isinstance(locations, list) else str(locations)
        jobs.append({
            "title":        j.get("title", ""),
            "company":      company,
            "location":     location_str or "Remote",
            "job_type":     j.get("jobType") or j.get("job_type", ""),
            "remote":       True,
            "description":  j.get("description", ""),
            "url":          j.get("url") or j.get("applicationLink", ""),
            "source":       "himalayas",
            "date_posted":  j.get("createdAt") or j.get("created_at", ""),
            "date_scraped": DATE_SCRAPED,
        })

    return [j for j in jobs if j["url"]], []


def run_arbeitnow(query: str = "") -> tuple:
    """
    Fetch Arbeitnow job board API (EU + remote jobs).
    Returns (jobs: list[dict], errors: list[str]).
    """
    try:
        resp = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            params={"page": 1},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            print("[scrapers] Arbeitnow 429 rate-limited — skipping")
            return [], ["Arbeitnow: rate-limited (429) — skipped"]
        print(f"[scrapers] Arbeitnow HTTP {status} error: {e}")
        return [], [f"Arbeitnow: HTTP {status} error — search failed"]
    except Exception as e:
        print(f"[scrapers] Arbeitnow error: {e}")
        return [], [f"Arbeitnow: unexpected error — {e}"]
    finally:
        time.sleep(1)

    raw_jobs = data.get("data", [])
    jobs = []
    for j in raw_jobs:
        job_types = j.get("job_types", [])
        job_type = job_types[0] if job_types else ""
        jobs.append({
            "title":        j.get("title", ""),
            "company":      j.get("company_name", ""),
            "location":     j.get("location", ""),
            "job_type":     job_type,
            "remote":       bool(j.get("remote", False)),
            "description":  j.get("description", ""),
            "url":          j.get("url", ""),
            "source":       "arbeitnow",
            "date_posted":  str(j.get("created_at", "")),
            "date_scraped": DATE_SCRAPED,
        })

    return [j for j in jobs if j["url"]], []
